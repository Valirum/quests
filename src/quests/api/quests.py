from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import validate_category_id
from quests.checks import normalize_check_fields
from quests.db import get_session, quest_load_options
from quests.emit import deliver_staged, stage_quest_diff, stage_simple
from quests.expire import expire_overdue_quests
from quests.hero import apply_quest_status_rewards, normalize_reward_attrs
from quests.models import (
    MetricLedger,
    Quest,
    QuestCreate,
    QuestRead,
    QuestStatus,
    QuestStep,
    QuestStepCreate,
    QuestStepUpdate,
    QuestUpdate,
    utcnow,
)
from quests.progress import clamp_step_progress, sync_status_from_steps
from quests.questlines import apply_questline_to_quest
from quests.serializers import quest_to_read
from quests.timeutil import ensure_utc, normalize_quest_deadline, to_db_utc

router = APIRouter(prefix="/api/quests", tags=["quests"])


def _apply_deadline(
    quest: Quest,
    *,
    duration_explicit: bool = False,
) -> None:
    """Store deadline as naive UTC; auto-fill duration (24h from now) when omitted."""
    deadline, duration = normalize_quest_deadline(
        deadline_at=quest.deadline_at,
        duration_seconds=quest.duration_seconds,
        duration_explicit=duration_explicit,
        now=utcnow(),
    )
    quest.deadline_at = deadline
    quest.duration_seconds = duration


def _source_label(*, quiet: bool, source: str | None) -> str | None:
    if source:
        return source
    return "quiet" if quiet else "api"


async def _get_quest_or_404(session: AsyncSession, quest_id: int) -> Quest:
    result = await session.exec(
        select(Quest).where(Quest.id == quest_id).options(*quest_load_options())
    )
    quest = result.first()
    if quest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found")
    return quest


@router.get("", response_model=list[QuestRead])
async def list_quests(
    status_filter: QuestStatus | None = Query(default=None, alias="status"),
    pinned: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[QuestRead]:
    # expire / materialize run in the maintenance loop — keep GET read-only.
    stmt = select(Quest).options(*quest_load_options()).order_by(Quest.sort_order, Quest.id)
    if status_filter is not None:
        stmt = stmt.where(Quest.status == status_filter)
    if pinned is not None:
        stmt = stmt.where(Quest.pinned == pinned)
    result = await session.exec(stmt)
    return [quest_to_read(q) for q in result.all()]


@router.get("/{quest_id}", response_model=QuestRead)
async def get_quest(
    quest_id: int,
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.post("", response_model=QuestRead, status_code=status.HTTP_201_CREATED)
async def create_quest(
    payload: QuestCreate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(
        default=None,
        description="Event source label (mcp, cli, web, …). Defaults from quiet.",
    ),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    data = payload.model_dump(exclude={"steps"})
    if "reward_attrs" in data:
        data["reward_attrs"] = normalize_reward_attrs(data.get("reward_attrs"))
    if "category_id" in data:
        data["category_id"] = await validate_category_id(session, data.get("category_id"))
    questline_id = data.pop("questline_id", None)
    quest = Quest(**data)
    await apply_questline_to_quest(session, quest, questline_id)
    _apply_deadline(
        quest,
        duration_explicit=payload.duration_seconds is not None,
    )
    if payload.steps:
        for i, step_data in enumerate(payload.steps):
            step_payload = step_data.model_dump()
            if step_payload.get("sort_order") is None:
                step_payload["sort_order"] = i
            quest.steps.append(QuestStep(**step_payload))
            normalize_check_fields(quest.steps[-1])
    else:
        quest.steps.append(
            QuestStep(title=quest.title, progress_current=0, progress_total=1, sort_order=0)
        )
    session.add(quest)
    await session.flush()
    qid = quest.id
    assert qid is not None
    # Reload with relationships — quest_to_read must not lazy-load in async.
    quest = await _get_quest_or_404(session, qid)
    read = quest_to_read(quest)
    src = _source_label(quiet=quiet, source=source)
    now = to_db_utc(utcnow())
    deadline = to_db_utc(ensure_utc(quest.deadline_at))
    already_due = (
        quest.status == QuestStatus.active
        and deadline is not None
        and now is not None
        and deadline <= now
    )
    staged: list = []
    if not already_due:
        staged.append(
            stage_simple(
                session,
                kind="quest_created",
                quest_id=read.id,
                title=read.title,
                description=read.description or "",
                detail="создано задание",
                sound="quest_created",
                toast=not quiet,
                source=src,
                significance=(
                    read.significance.value
                    if hasattr(read.significance, "value")
                    else str(read.significance or "common")
                ),
            )
        )
    await session.commit()
    expired_ids = await expire_overdue_quests(session)
    if qid in expired_ids:
        return quest_to_read(await _get_quest_or_404(session, qid))
    await deliver_staged(staged)
    return quest_to_read(await _get_quest_or_404(session, qid))


@router.patch("/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: int,
    payload: QuestUpdate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(
        default=None,
        description="Event source label (mcp, cli, web, …). Defaults from quiet.",
    ),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    quest = await _get_quest_or_404(session, quest_id)
    before = quest_to_read(quest)

    incoming = payload.model_dump(exclude_unset=True)
    duration_explicit = "duration_seconds" in incoming
    deadline_touched = "deadline_at" in incoming

    data = dict(incoming)
    if "reward_attrs" in data:
        data["reward_attrs"] = normalize_reward_attrs(data.get("reward_attrs"))
    if "category_id" in data:
        data["category_id"] = await validate_category_id(session, data.get("category_id"))
    questline_touched = "questline_id" in data
    questline_id = data.pop("questline_id", None) if questline_touched else None
    before_status = quest.status
    for key, value in data.items():
        setattr(quest, key, value)
    if questline_touched:
        await apply_questline_to_quest(session, quest, questline_id)
    elif quest.questline_id is not None and "category_id" in data:
        await apply_questline_to_quest(session, quest, quest.questline_id)

    if quest.status == QuestStatus.completed and quest.completed_at is None:
        quest.completed_at = utcnow()
    if quest.status != QuestStatus.completed:
        quest.completed_at = None

    quest.updated_at = utcnow()
    if deadline_touched or duration_explicit or (
        quest.deadline_at is not None and quest.duration_seconds is None
    ):
        _apply_deadline(quest, duration_explicit=duration_explicit)

    if before_status != quest.status:
        await apply_quest_status_rewards(session, quest, new_status=quest.status)

    session.add(quest)
    read = quest_to_read(quest)
    staged = stage_quest_diff(
        session,
        before,
        read,
        quiet=quiet,
        source=_source_label(quiet=quiet, source=source),
    )
    await session.commit()
    await deliver_staged(staged)
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.post("/{quest_id}/steps", response_model=QuestRead, status_code=status.HTTP_201_CREATED)
async def add_quest_step(
    quest_id: int,
    payload: QuestStepCreate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    quest = await _get_quest_or_404(session, quest_id)
    before = quest_to_read(quest)
    before_status = quest.status

    step_payload = payload.model_dump()
    explicit = payload.model_dump(exclude_unset=True)
    if "sort_order" not in explicit:
        next_order = 0
        if quest.steps:
            next_order = max(int(s.sort_order or 0) for s in quest.steps) + 1
        step_payload["sort_order"] = next_order
    step = QuestStep(**step_payload)
    clamp_step_progress(step)
    normalize_check_fields(step)
    quest.steps.append(step)
    sync_status_from_steps(quest)

    if before_status != quest.status:
        await apply_quest_status_rewards(session, quest, new_status=quest.status)

    quest.updated_at = utcnow()
    session.add(quest)
    await session.flush()
    read = quest_to_read(quest)
    staged = stage_quest_diff(
        session,
        before,
        read,
        quiet=quiet,
        source=_source_label(quiet=quiet, source=source),
    )
    await session.commit()
    await deliver_staged(staged)
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.patch("/{quest_id}/steps/{step_id}", response_model=QuestRead)
async def update_quest_step(
    quest_id: int,
    step_id: int,
    payload: QuestStepUpdate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    quest = await _get_quest_or_404(session, quest_id)
    before = quest_to_read(quest)
    before_status = quest.status
    step = next((s for s in quest.steps if s.id == step_id), None)
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(step, key, value)
    clamp_step_progress(step)
    normalize_check_fields(step)
    sync_status_from_steps(quest)

    if before_status != quest.status:
        await apply_quest_status_rewards(session, quest, new_status=quest.status)

    quest.updated_at = utcnow()
    session.add(quest)
    read = quest_to_read(quest)
    staged = stage_quest_diff(
        session,
        before,
        read,
        quiet=quiet,
        source=_source_label(quiet=quiet, source=source),
    )
    await session.commit()
    await deliver_staged(staged)
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.delete("/{quest_id}/steps/{step_id}", response_model=QuestRead)
async def delete_quest_step(
    quest_id: int,
    step_id: int,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    quest = await _get_quest_or_404(session, quest_id)
    before = quest_to_read(quest)
    before_status = quest.status
    step = next((s for s in quest.steps if s.id == step_id), None)
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    if len(quest.steps) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last step",
        )

    quest.steps.remove(step)
    await session.delete(step)
    sync_status_from_steps(quest)

    if before_status != quest.status:
        await apply_quest_status_rewards(session, quest, new_status=quest.status)

    quest.updated_at = utcnow()
    session.add(quest)
    read = quest_to_read(quest)
    staged = stage_quest_diff(
        session,
        before,
        read,
        quiet=quiet,
        source=_source_label(quiet=quiet, source=source),
    )
    await session.commit()
    await deliver_staged(staged)
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quest(
    quest_id: int,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    quest = await _get_quest_or_404(session, quest_id)
    title = quest.title
    description = quest.description or ""
    staged = [
        stage_simple(
            session,
            kind="quest_deleted",
            quest_id=quest_id,
            title=title,
            description=description,
            detail="удалено",
            sound="quest_deleted",
            toast=not quiet,
            source=_source_label(quiet=quiet, source=source),
        )
    ]
    await session.exec(delete(MetricLedger).where(MetricLedger.quest_id == quest_id))
    await session.delete(quest)
    await session.commit()
    await deliver_staged(staged)
