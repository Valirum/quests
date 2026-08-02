from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.checks import normalize_check_fields
from quests.db import get_session
from quests.models import (
    QuestTemplate,
    QuestTemplateCreate,
    QuestTemplateRead,
    QuestTemplateStep,
    QuestTemplateStepCreate,
    QuestTemplateStepRead,
    QuestTemplateUpdate,
    TemplateEmitMode,
    utcnow,
)
from quests.periodic import (
    clamp_emit_chance,
    materialize_due,
    normalize_deadline_time,
    normalize_emit_mode,
    normalize_progress_range,
    parse_weekdays,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


def template_load_options():
    return selectinload(QuestTemplate.steps)


def _step_to_read(step: QuestTemplateStep) -> QuestTemplateStepRead:
    return QuestTemplateStepRead(
        id=step.id,  # type: ignore[arg-type]
        template_id=step.template_id,  # type: ignore[arg-type]
        title=step.title,
        description=step.description,
        progress_min=max(1, int(step.progress_min or 1)),
        progress_max=max(1, int(step.progress_max or step.progress_min or 1)),
        sort_order=step.sort_order,
        check_command=step.check_command,
        check_interval_seconds=step.check_interval_seconds,
    )


def template_to_read(tmpl: QuestTemplate) -> QuestTemplateRead:
    steps = sorted(tmpl.steps or [], key=lambda s: (s.sort_order, s.id or 0))
    return QuestTemplateRead(
        id=tmpl.id,  # type: ignore[arg-type]
        title=tmpl.title,
        description=tmpl.description,
        pinned=tmpl.pinned,
        significance=tmpl.significance,
        sort_order=tmpl.sort_order,
        deadline_time=tmpl.deadline_time,
        duration_seconds=tmpl.duration_seconds,
        freq=tmpl.freq,
        weekdays=tmpl.weekdays,
        enabled=tmpl.enabled,
        timezone=tmpl.timezone,
        emit_mode=normalize_emit_mode(tmpl.emit_mode),
        emit_chance=clamp_emit_chance(tmpl.emit_chance, 1.0),
        emit_window_start=tmpl.emit_window_start,
        emit_window_end=tmpl.emit_window_end,
        created_at=tmpl.created_at,
        updated_at=tmpl.updated_at,
        steps=[_step_to_read(s) for s in steps],
    )


def _normalize_weekdays(raw: str | None, *, freq: str) -> str:
    if freq == "daily":
        return "0,1,2,3,4,5,6"
    days = sorted(parse_weekdays(raw or ""))
    if not days:
        days = [0, 1, 2, 3, 4]  # weekdays default for weekly
    return ",".join(str(d) for d in days)


def _step_from_create(step_data: QuestTemplateStepCreate, *, index: int) -> QuestTemplateStep:
    payload = step_data.model_dump()
    progress_total = payload.pop("progress_total", None)
    lo, hi = normalize_progress_range(
        progress_min=payload.pop("progress_min", None),
        progress_max=payload.pop("progress_max", None),
        progress_total=progress_total,
    )
    if payload.get("sort_order") is None:
        payload["sort_order"] = index
    step = QuestTemplateStep(
        **payload,
        progress_min=lo,
        progress_max=hi,
    )
    normalize_check_fields(step)
    return step


def _apply_steps(tmpl: QuestTemplate, steps: list[QuestTemplateStepCreate] | None) -> None:
    tmpl.steps.clear()
    if not steps:
        tmpl.steps.append(
            QuestTemplateStep(
                title=tmpl.title,
                progress_min=1,
                progress_max=1,
                sort_order=0,
            )
        )
        return
    for i, step_data in enumerate(steps):
        tmpl.steps.append(_step_from_create(step_data, index=i))


def _normalize_template_timing(data: dict, *, emit_mode: TemplateEmitMode) -> None:
    data["emit_mode"] = emit_mode
    data["emit_chance"] = clamp_emit_chance(data.get("emit_chance"), 1.0)
    data["emit_window_start"] = normalize_deadline_time(data.get("emit_window_start"))
    data["emit_window_end"] = normalize_deadline_time(data.get("emit_window_end"))
    if emit_mode == TemplateEmitMode.surprise:
        data["deadline_time"] = None
        if data.get("duration_seconds") is not None:
            data["duration_seconds"] = max(1, int(data["duration_seconds"]))
        return
    data["deadline_time"] = normalize_deadline_time(data.get("deadline_time"))
    if data["deadline_time"] is None:
        data["duration_seconds"] = None
    elif data.get("duration_seconds") is not None:
        data["duration_seconds"] = max(1, int(data["duration_seconds"]))


async def _get_template_or_404(session: AsyncSession, template_id: int) -> QuestTemplate:
    result = await session.exec(
        select(QuestTemplate)
        .where(QuestTemplate.id == template_id)
        .options(template_load_options())
    )
    tmpl = result.first()
    if tmpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tmpl


@router.get("", response_model=list[QuestTemplateRead])
async def list_templates(
    enabled: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[QuestTemplateRead]:
    stmt = (
        select(QuestTemplate)
        .options(template_load_options())
        .order_by(QuestTemplate.sort_order, QuestTemplate.id)
    )
    if enabled is not None:
        stmt = stmt.where(QuestTemplate.enabled == enabled)
    result = await session.exec(stmt)
    return [template_to_read(t) for t in result.all()]


@router.get("/{template_id}", response_model=QuestTemplateRead)
async def get_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
) -> QuestTemplateRead:
    return template_to_read(await _get_template_or_404(session, template_id))


@router.post(
    "/{template_id}/copy",
    response_model=QuestTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def copy_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
) -> QuestTemplateRead:
    """Clone template; copy is always disabled so it won't materialize immediately."""
    src = await _get_template_or_404(session, template_id)
    freq = str(src.freq.value if hasattr(src.freq, "value") else src.freq)
    emit_mode = normalize_emit_mode(src.emit_mode)
    clone = QuestTemplate(
        title=_copy_title(src.title),
        description=src.description or "",
        pinned=bool(src.pinned),
        significance=src.significance,
        sort_order=int(src.sort_order or 0),
        deadline_time=(
            None
            if emit_mode == TemplateEmitMode.surprise
            else normalize_deadline_time(src.deadline_time)
        ),
        duration_seconds=(
            max(1, int(src.duration_seconds))
            if src.duration_seconds is not None
            and (
                emit_mode == TemplateEmitMode.surprise
                or bool(src.deadline_time)
            )
            else None
        ),
        freq=src.freq,
        weekdays=_normalize_weekdays(src.weekdays, freq=freq),
        enabled=False,
        timezone=src.timezone or "Europe/Moscow",
        emit_mode=emit_mode,
        emit_chance=clamp_emit_chance(src.emit_chance, 1.0),
        emit_window_start=normalize_deadline_time(src.emit_window_start),
        emit_window_end=normalize_deadline_time(src.emit_window_end),
    )
    steps_src = sorted(src.steps or [], key=lambda s: (s.sort_order, s.id or 0))
    _apply_steps(
        clone,
        [
            QuestTemplateStepCreate(
                title=s.title,
                description=s.description or "",
                progress_min=max(1, int(s.progress_min or 1)),
                progress_max=max(
                    1, int(s.progress_max or s.progress_min or 1)
                ),
                sort_order=int(s.sort_order if s.sort_order is not None else i),
                check_command=s.check_command,
                check_interval_seconds=s.check_interval_seconds,
            )
            for i, s in enumerate(steps_src)
        ]
        or None,
    )
    session.add(clone)
    await session.commit()
    tid = clone.id
    assert tid is not None
    return template_to_read(await _get_template_or_404(session, tid))


def _copy_title(title: str) -> str:
    base = (title or "").strip() or "Шаблон"
    suffix = " (копия)"
    max_len = 200
    if len(base) + len(suffix) <= max_len:
        return base + suffix
    return base[: max_len - len(suffix)].rstrip() + suffix


@router.post("", response_model=QuestTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: QuestTemplateCreate,
    session: AsyncSession = Depends(get_session),
) -> QuestTemplateRead:
    data = payload.model_dump(exclude={"steps"})
    freq = str(data.get("freq") or "daily")
    data["weekdays"] = _normalize_weekdays(data.get("weekdays"), freq=freq)
    emit_mode = normalize_emit_mode(data.get("emit_mode"))
    _normalize_template_timing(data, emit_mode=emit_mode)
    tmpl = QuestTemplate(**data)
    _apply_steps(tmpl, list(payload.steps) if payload.steps else None)
    session.add(tmpl)
    await session.commit()
    tid = tmpl.id
    assert tid is not None
    read = template_to_read(await _get_template_or_404(session, tid))
    if read.enabled:
        await materialize_due(session)
    return read


@router.patch("/{template_id}", response_model=QuestTemplateRead)
async def update_template(
    template_id: int,
    payload: QuestTemplateUpdate,
    session: AsyncSession = Depends(get_session),
) -> QuestTemplateRead:
    tmpl = await _get_template_or_404(session, template_id)
    incoming = payload.model_dump(exclude_unset=True)
    steps_touched = "steps" in incoming
    data = {k: v for k, v in incoming.items() if k != "steps"}

    emit_mode = normalize_emit_mode(
        data.get("emit_mode", tmpl.emit_mode)
    )
    # Merge timing fields for normalization when any of them change.
    timing_keys = {
        "emit_mode",
        "emit_chance",
        "emit_window_start",
        "emit_window_end",
        "deadline_time",
        "duration_seconds",
    }
    if timing_keys & data.keys() or "emit_mode" in data:
        merged = {
            "emit_mode": emit_mode,
            "emit_chance": data.get("emit_chance", tmpl.emit_chance),
            "emit_window_start": data.get(
                "emit_window_start", tmpl.emit_window_start
            ),
            "emit_window_end": data.get("emit_window_end", tmpl.emit_window_end),
            "deadline_time": data.get("deadline_time", tmpl.deadline_time),
            "duration_seconds": data.get(
                "duration_seconds", tmpl.duration_seconds
            ),
        }
        _normalize_template_timing(merged, emit_mode=emit_mode)
        data.update(merged)

    for key, value in data.items():
        setattr(tmpl, key, value)
    freq = str(tmpl.freq.value if hasattr(tmpl.freq, "value") else tmpl.freq)
    if "weekdays" in data or "freq" in data:
        tmpl.weekdays = _normalize_weekdays(tmpl.weekdays, freq=freq)

    emit_mode = normalize_emit_mode(tmpl.emit_mode)
    if emit_mode == TemplateEmitMode.surprise:
        tmpl.deadline_time = None
        if tmpl.duration_seconds is not None:
            tmpl.duration_seconds = max(1, int(tmpl.duration_seconds))
    elif tmpl.deadline_time is None:
        tmpl.duration_seconds = None
    elif tmpl.duration_seconds is not None:
        tmpl.duration_seconds = max(1, int(tmpl.duration_seconds))

    if steps_touched:
        _apply_steps(tmpl, list(payload.steps) if payload.steps is not None else None)
    tmpl.updated_at = utcnow()
    session.add(tmpl)
    await session.commit()
    read = template_to_read(await _get_template_or_404(session, template_id))
    if read.enabled:
        await materialize_due(session)
    return read


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    from quests.models import TemplateEmitRoll
    from sqlmodel import delete

    tmpl = await _get_template_or_404(session, template_id)
    await session.exec(
        delete(TemplateEmitRoll).where(TemplateEmitRoll.template_id == template_id)
    )
    await session.delete(tmpl)
    await session.commit()
