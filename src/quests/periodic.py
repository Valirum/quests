"""Materialize quest instances from periodic templates."""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, time, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal, quest_load_options
from quests.emit import deliver_staged, stage_simple
from quests.models import (
    Quest,
    QuestStatus,
    QuestStep,
    QuestTemplate,
    TemplateEmitMode,
    TemplateEmitOutcome,
    TemplateEmitRoll,
    TemplateFreq,
    utcnow,
)
from quests.serializers import quest_to_read
from quests.timeutil import to_db_utc

DEFAULT_TZ = os.environ.get("QUESTS_TZ", "Europe/Moscow")


def parse_weekdays(raw: str) -> set[int]:
    out: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            day = int(part)
        except ValueError:
            continue
        if 0 <= day <= 6:
            out.add(day)
    return out


def resolve_tz(name: str | None) -> ZoneInfo:
    for candidate in (name, DEFAULT_TZ, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except ZoneInfoNotFoundError:
            continue
    return ZoneInfo("UTC")


def period_key_for(local_dt: datetime) -> str:
    return local_dt.date().isoformat()


def parse_deadline_time(raw: str | None) -> time | None:
    """Parse 'HH:MM' / 'HH:MM:SS'. Empty/None → no deadline."""
    text = (raw or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return None
    return time(hour, minute, second)


def normalize_deadline_time(raw: str | None) -> str | None:
    parsed = parse_deadline_time(raw)
    if parsed is None:
        return None
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def normalize_emit_mode(raw: Any) -> TemplateEmitMode:
    text = str(getattr(raw, "value", raw) or "").strip().lower()
    if text in {"surprise", "random", "chance"}:
        return TemplateEmitMode.surprise
    return TemplateEmitMode.fixed


def clamp_emit_chance(raw: Any, default: float = 1.0) -> float:
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return default


def deadline_for_period(local_dt: datetime, deadline_time_raw: str | None) -> datetime | None:
    """Aware local deadline for the period day, or None if no time set."""
    clock = parse_deadline_time(deadline_time_raw)
    if clock is None:
        return None
    return datetime.combine(local_dt.date(), clock, tzinfo=local_dt.tzinfo)


def template_due_today(template: QuestTemplate, local_now: datetime) -> bool:
    if template.freq == TemplateFreq.daily:
        return True
    days = parse_weekdays(template.weekdays)
    if not days:
        days = {0, 1, 2, 3, 4, 5, 6}
    return local_now.weekday() in days


def resolve_progress_total(step: Any, *, rng: random.Random | None = None) -> int:
    """Pick progress_total from template step min..max (inclusive)."""
    lo_raw = getattr(step, "progress_min", None)
    hi_raw = getattr(step, "progress_max", None)
    if lo_raw is None and hi_raw is None:
        legacy = getattr(step, "progress_total", None)
        lo = max(1, int(legacy or 1))
        hi = lo
    else:
        lo = max(1, int(lo_raw if lo_raw is not None else 1))
        hi = max(1, int(hi_raw if hi_raw is not None else lo))
    if hi < lo:
        lo, hi = hi, lo
    picker = rng if rng is not None else random
    return picker.randint(lo, hi)


def normalize_progress_range(
    *,
    progress_min: int | None = None,
    progress_max: int | None = None,
    progress_total: int | None = None,
) -> tuple[int, int]:
    """Resolve create/update payload into inclusive (min, max)."""
    if progress_min is None and progress_max is None:
        total = max(1, int(progress_total or 1))
        return total, total
    lo = max(1, int(progress_min if progress_min is not None else progress_total or 1))
    hi = max(1, int(progress_max if progress_max is not None else lo))
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def parse_progress_range_text(raw: str | int | None) -> tuple[int, int]:
    """Parse 'n' or 'n..m' / 'n-m' into (min, max)."""
    if isinstance(raw, int):
        n = max(1, raw)
        return n, n
    text = str(raw or "").strip()
    if not text:
        return 1, 1
    for sep in ("..", "-", "–", "—"):
        if sep in text:
            left, right = text.split(sep, 1)
            try:
                lo = max(1, int(left.strip()))
                hi = max(1, int(right.strip()))
            except ValueError:
                return 1, 1
            if hi < lo:
                lo, hi = hi, lo
            return lo, hi
    try:
        n = max(1, int(text))
    except ValueError:
        return 1, 1
    return n, n


def pick_scheduled_at(
    local_day: datetime,
    window_start_raw: str | None,
    window_end_raw: str | None,
    *,
    rng: random.Random | None = None,
) -> datetime:
    """Aware local datetime uniformly in [start, end] on local_day's date."""
    start_clock = parse_deadline_time(window_start_raw) or time(0, 0, 0)
    end_clock = parse_deadline_time(window_end_raw) or time(23, 59, 0)
    start_dt = datetime.combine(local_day.date(), start_clock, tzinfo=local_day.tzinfo)
    end_dt = datetime.combine(local_day.date(), end_clock, tzinfo=local_day.tzinfo)
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt
    span = int((end_dt - start_dt).total_seconds())
    picker = rng if rng is not None else random
    offset = picker.randint(0, max(0, span))
    return start_dt + timedelta(seconds=offset)


def surprise_ready(roll: TemplateEmitRoll, now_utc: datetime) -> bool:
    """True when a scheduled roll may materialize."""
    if roll.outcome != TemplateEmitOutcome.scheduled:
        return False
    if roll.scheduled_at is None:
        return True
    scheduled = roll.scheduled_at
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    else:
        scheduled = scheduled.astimezone(timezone.utc)
    return now_utc >= scheduled


def template_load_options():
    return (
        selectinload(QuestTemplate.steps),
        selectinload(QuestTemplate.category),
        selectinload(QuestTemplate.questline),
    )


def _fixed_deadline(
    tmpl: QuestTemplate,
    local_now: datetime,
    tz: ZoneInfo,
) -> tuple[datetime | None, int | None]:
    deadline_local = deadline_for_period(local_now, tmpl.deadline_time)
    if deadline_local is None:
        return None, None
    deadline_utc = to_db_utc(deadline_local.astimezone(timezone.utc))
    assert deadline_utc is not None
    if tmpl.duration_seconds is not None:
        duration = max(1, int(tmpl.duration_seconds))
    else:
        start_local = datetime.combine(local_now.date(), time(0, 0, 0), tzinfo=tz)
        if deadline_local <= start_local:
            start_local = local_now
        duration = max(60, int((deadline_local - start_local).total_seconds()))
    return deadline_utc, duration


def _surprise_deadline(
    tmpl: QuestTemplate,
    now_utc: datetime,
) -> tuple[datetime | None, int | None]:
    if tmpl.duration_seconds is None:
        return None, None
    duration = max(1, int(tmpl.duration_seconds))
    deadline_utc = to_db_utc(now_utc + timedelta(seconds=duration))
    return deadline_utc, duration


def _build_quest_steps(tmpl: QuestTemplate, *, rng: random.Random | None = None) -> list[QuestStep]:
    steps_src = sorted(tmpl.steps or [], key=lambda s: (s.sort_order, s.id or 0))
    if not steps_src:
        return [
            QuestStep(
                title=tmpl.title,
                progress_current=0,
                progress_total=1,
                sort_order=0,
            )
        ]
    return [
        QuestStep(
            title=s.title,
            description=s.description or "",
            progress_current=0,
            progress_total=resolve_progress_total(s, rng=rng),
            sort_order=int(s.sort_order if s.sort_order is not None else i),
            check_command=(s.check_command or None),
            check_interval_seconds=s.check_interval_seconds,
        )
        for i, s in enumerate(steps_src)
    ]


async def _get_emit_roll(
    session: AsyncSession,
    template_id: int,
    period_key: str,
) -> TemplateEmitRoll | None:
    result = await session.exec(
        select(TemplateEmitRoll)
        .where(TemplateEmitRoll.template_id == template_id)
        .where(TemplateEmitRoll.period_key == period_key)
        .limit(1)
    )
    return result.first()


async def _ensure_surprise_roll(
    session: AsyncSession,
    tmpl: QuestTemplate,
    *,
    period_key: str,
    local_now: datetime,
    rng: random.Random | None = None,
) -> TemplateEmitRoll:
    existing = await _get_emit_roll(session, int(tmpl.id), period_key)  # type: ignore[arg-type]
    if existing is not None:
        return existing

    picker = rng if rng is not None else random
    chance = clamp_emit_chance(tmpl.emit_chance, 1.0)
    if picker.random() >= chance:
        roll = TemplateEmitRoll(
            template_id=int(tmpl.id),  # type: ignore[arg-type]
            period_key=period_key,
            outcome=TemplateEmitOutcome.miss,
            scheduled_at=None,
        )
    else:
        scheduled_local = pick_scheduled_at(
            local_now,
            tmpl.emit_window_start,
            tmpl.emit_window_end,
            rng=picker,
        )
        scheduled_utc = to_db_utc(scheduled_local.astimezone(timezone.utc))
        roll = TemplateEmitRoll(
            template_id=int(tmpl.id),  # type: ignore[arg-type]
            period_key=period_key,
            outcome=TemplateEmitOutcome.scheduled,
            scheduled_at=scheduled_utc,
        )
    session.add(roll)
    await session.flush()
    return roll


async def _materialize(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[int]:
    now_utc = ensure_aware_utc(now)
    result = await session.exec(
        select(QuestTemplate)
        .where(QuestTemplate.enabled == True)  # noqa: E712
        .options(*template_load_options())
        .order_by(QuestTemplate.sort_order, QuestTemplate.id)
    )
    templates = list(result.all())
    created_ids: list[int] = []
    staged: list = []

    for tmpl in templates:
        tz = resolve_tz(tmpl.timezone)
        local_now = now_utc.astimezone(tz)
        if not template_due_today(tmpl, local_now):
            continue
        key = period_key_for(local_now)

        existing = await session.exec(
            select(Quest.id)
            .where(Quest.template_id == tmpl.id)
            .where(Quest.period_key == key)
            .limit(1)
        )
        if existing.first() is not None:
            continue

        emit_mode = normalize_emit_mode(tmpl.emit_mode)
        surprise_roll: TemplateEmitRoll | None = None

        if emit_mode == TemplateEmitMode.surprise:
            surprise_roll = await _ensure_surprise_roll(
                session,
                tmpl,
                period_key=key,
                local_now=local_now,
                rng=rng,
            )
            if surprise_roll.outcome == TemplateEmitOutcome.miss:
                continue
            if surprise_roll.outcome == TemplateEmitOutcome.materialized:
                continue
            if not surprise_ready(surprise_roll, now_utc):
                continue
            deadline_utc, duration = _surprise_deadline(tmpl, now_utc)
        else:
            deadline_utc, duration = _fixed_deadline(tmpl, local_now, tz)

        quest = Quest(
            title=tmpl.title,
            description=tmpl.description or "",
            status=QuestStatus.active,
            significance=tmpl.significance,
            pinned=bool(tmpl.pinned),
            sort_order=int(tmpl.sort_order or 0),
            deadline_at=deadline_utc,
            duration_seconds=duration,
            reward_attrs=tmpl.reward_attrs,
            category_id=tmpl.category_id,
            questline_id=tmpl.questline_id,
            template_id=tmpl.id,
            period_key=key,
            steps=_build_quest_steps(tmpl, rng=rng),
        )
        session.add(quest)
        await session.flush()
        assert quest.id is not None
        created_ids.append(int(quest.id))
        if surprise_roll is not None:
            surprise_roll.outcome = TemplateEmitOutcome.materialized
            surprise_roll.updated_at = utcnow()
            session.add(surprise_roll)

        loaded = await session.exec(
            select(Quest)
            .where(Quest.id == quest.id)
            .options(*quest_load_options())
        )
        full = loaded.first()
        assert full is not None
        read = quest_to_read(full)
        staged.append(
            stage_simple(
                session,
                kind="quest_appeared",
                quest_id=read.id,
                title=read.title,
                description=read.description or "",
                detail=f"Период {read.period_key or ''}".strip(),
                sound="quest_created",
                toast=True,
                source="system",
                significance=(
                    read.significance.value
                    if hasattr(read.significance, "value")
                    else str(read.significance or "common")
                ),
            )
        )

    await session.commit()
    await deliver_staged(staged)
    return created_ids


def ensure_aware_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


async def materialize_due(
    session: AsyncSession | None = None,
    *,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[int]:
    """Create missing instances for the current local period. Returns new quest ids."""
    if session is not None:
        return await _materialize(session, now=now, rng=rng)
    async with SessionLocal() as session:
        return await _materialize(session, now=now, rng=rng)
