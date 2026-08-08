from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import validate_category_id
from quests.checks import normalize_check_fields
from quests.db import get_session, quest_load_options
from quests.events import hub
from quests.expire import expire_overdue_quests
from quests.hero import apply_quest_status_rewards, normalize_reward_attrs
from quests.models import (
    MetricLedger,
    Quest,
    QuestCreate,
    QuestRead,
    QuestStatus,
    QuestStep,
    QuestStepUpdate,
    QuestUpdate,
    utcnow,
)
from quests.notify import quest_change_events
from quests.periodic import materialize_due
from quests.progress import clamp_step_progress, sync_status_from_steps
from quests.questlines import apply_questline_to_quest
from quests.serializers import quest_to_read
from quests.timeutil import auto_duration_seconds, ensure_utc, to_db_utc

router = APIRouter(prefix="/api/quests", tags=["quests"])


def _normalize_deadline(quest: Quest, *, duration_explicit: bool = False) -> None:
    """Store deadline as naive UTC; auto-fill duration from created/changed when needed."""
    if quest.deadline_at is None:
        quest.duration_seconds = None
        return
    quest.deadline_at = to_db_utc(quest.deadline_at)
    if duration_explicit and quest.duration_seconds is not None:
        quest.duration_seconds = max(1, int(quest.duration_seconds))
        return
    if quest.duration_seconds is None:
        anchor = ensure_utc(quest.created_at) or ensure_utc(utcnow())
        deadline = ensure_utc(quest.deadline_at)
        assert deadline is not None and anchor is not None
        if deadline <= anchor:
            anchor = ensure_utc(utcnow())
            assert anchor is not None
        quest.duration_seconds = auto_duration_seconds(deadline, anchor)


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
    await expire_overdue_quests(session)
    await materialize_due(session)
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
    await expire_overdue_quests(session)
    await materialize_due(session)
    return quest_to_read(await _get_quest_or_404(session, quest_id))


@router.post("", response_model=QuestRead, status_code=status.HTTP_201_CREATED)
async def create_quest(
    payload: QuestCreate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    data = payload.model_dump(exclude={"steps"})
    if data.get("deadline_at") is not None:
        data["deadline_at"] = to_db_utc(data["deadline_at"])
    if "reward_attrs" in data:
        data["reward_attrs"] = normalize_reward_attrs(data.get("reward_attrs"))
    if "category_id" in data:
        data["category_id"] = await validate_category_id(session, data.get("category_id"))
    questline_id = data.pop("questline_id", None)
    quest = Quest(**data)
    await apply_questline_to_quest(session, quest, questline_id)
    _normalize_deadline(
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
    await session.commit()
    qid = quest.id
    assert qid is not None
    expired_ids = await expire_overdue_quests(session)
    read = quest_to_read(await _get_quest_or_404(session, qid))
    if qid not in expired_ids:
        await hub.publish(
            "quest_created",
            quest_id=read.id,
            title=read.title,
            description=read.description or "",
            detail="создано задание",
            sound="quest_created",
            toast=not quiet,
            significance=(
                read.significance.value
                if hasattr(read.significance, "value")
                else str(read.significance or "common")
            ),
        )
    return read


@router.patch("/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: int,
    payload: QuestUpdate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    session: AsyncSession = Depends(get_session),
) -> QuestRead:
    quest = await _get_quest_or_404(session, quest_id)
    before = quest_to_read(quest)

    incoming = payload.model_dump(exclude_unset=True)
    status_explicit = "status" in incoming
    steps_touched = "steps" in incoming
    duration_explicit = "duration_seconds" in incoming
    deadline_touched = "deadline_at" in incoming

    data = {k: v for k, v in incoming.items() if k != "steps"}
    if "deadline_at" in data and data["deadline_at"] is not None:
        data["deadline_at"] = to_db_utc(data["deadline_at"])
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
        # Member quests cannot diverge from line category.
        await apply_questline_to_quest(session, quest, quest.questline_id)

    if steps_touched:
        quest.steps.clear()
        for i, step_data in enumerate(payload.steps or []):
            step_payload = step_data.model_dump()
            if step_payload.get("sort_order") is None:
                step_payload["sort_order"] = i
            step = QuestStep(**step_payload)
            clamp_step_progress(step)
            normalize_check_fields(step)
            quest.steps.append(step)

    if steps_touched and not status_explicit:
        sync_status_from_steps(quest)
    else:
        if quest.status == QuestStatus.completed and quest.completed_at is None:
            quest.completed_at = utcnow()
        if quest.status != QuestStatus.completed:
            quest.completed_at = None

    quest.updated_at = utcnow()
    if quest.deadline_at is None:
        quest.duration_seconds = None
    else:
        quest.deadline_at = to_db_utc(quest.deadline_at)
        if duration_explicit and quest.duration_seconds is not None:
            quest.duration_seconds = max(1, int(quest.duration_seconds))
        elif quest.duration_seconds is None or (deadline_touched and not duration_explicit):
            # No duration (or deadline changed without one) → deadline − created/changed.
            anchor = quest.updated_at if deadline_touched else (quest.created_at or quest.updated_at)
            assert quest.deadline_at is not None
            deadline = ensure_utc(quest.deadline_at)
            anchor_utc = ensure_utc(anchor)
            assert deadline is not None and anchor_utc is not None
            if deadline <= anchor_utc:
                anchor_utc = ensure_utc(quest.updated_at)
                assert anchor_utc is not None
            quest.duration_seconds = auto_duration_seconds(deadline, anchor_utc)

    if before_status != quest.status:
        await apply_quest_status_rewards(session, quest, new_status=quest.status)

    session.add(quest)
    await session.commit()
    read = quest_to_read(await _get_quest_or_404(session, quest_id))
    await _publish_changes(before, read, quiet=quiet)
    return read


@router.patch("/{quest_id}/steps/{step_id}", response_model=QuestRead)
async def update_quest_step(
    quest_id: int,
    step_id: int,
    payload: QuestStepUpdate,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
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
    await session.commit()
    read = quest_to_read(await _get_quest_or_404(session, quest_id))
    await _publish_changes(before, read, quiet=quiet)
    return read


async def _publish_changes(
    before: QuestRead,
    read: QuestRead,
    *,
    quiet: bool = False,
) -> None:
    for ev in quest_change_events(before, read):
        toast = False if quiet else bool(ev.get("toast", True))
        await hub.publish(
            ev["kind"],
            quest_id=read.id,
            title=ev.get("title", read.title),
            description=ev.get("description", read.description or ""),
            detail=ev.get("detail", ""),
            sound=ev.get("sound"),
            toast=toast,
            step_title=ev.get("step_title"),
            significance=ev.get("significance"),
        )


@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quest(
    quest_id: int,
    quiet: bool = Query(
        default=False,
        description="If true — publish without overlay toasts (HUD still refreshes).",
    ),
    session: AsyncSession = Depends(get_session),
) -> None:
    quest = await _get_quest_or_404(session, quest_id)
    title = quest.title
    description = quest.description or ""
    await session.exec(delete(MetricLedger).where(MetricLedger.quest_id == quest_id))
    await session.delete(quest)
    await session.commit()
    await hub.publish(
        "quest_deleted",
        quest_id=quest_id,
        title=title,
        description=description,
        detail="удалено",
        sound="quest_deleted",
        toast=not quiet,
    )
