"""Aggregate quest activity + periodic template streaks for /api/stats."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.models import Quest, QuestChangeLog, QuestStatus, QuestTemplate
from quests.periodic import resolve_tz
from quests.timeutil import ensure_utc, remaining_seconds

UTC = timezone.utc

ISSUED_KINDS = frozenset({"quest_created", "quest_appeared"})
COMPLETED_KIND = "quest_completed"
FAILED_KIND = "quest_failed"


def local_day(dt: datetime, tz: ZoneInfo) -> date:
    aware = ensure_utc(dt)
    assert aware is not None
    return aware.astimezone(tz).date()


def resolve_range(
    *,
    days: int | None,
    date_from: date | None,
    date_to: date | None,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> tuple[date, date]:
    now = ensure_utc(now or datetime.now(UTC))
    assert now is not None
    today = now.astimezone(tz).date()
    end = date_to or today
    if date_from is not None:
        start = date_from
    else:
        n = max(1, int(days or 30))
        start = end - timedelta(days=n - 1)
    if start > end:
        start, end = end, start
    return start, end


def range_bounds_utc(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Inclusive local dates → half-open UTC [start, end_exclusive)."""
    start_local = datetime.combine(start, time.min, tzinfo=tz)
    end_exclusive_local = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(UTC), end_exclusive_local.astimezone(UTC)


def instance_outcome(quest: Quest, *, now: datetime | None = None) -> str:
    """completed | miss | open — only for periods that have an instance."""
    now = ensure_utc(now or datetime.now(UTC))
    status = quest.status
    if status == QuestStatus.completed:
        return "completed"
    if status in (QuestStatus.failed, QuestStatus.delayed, QuestStatus.archived):
        return "miss"
    rem = remaining_seconds(quest.deadline_at, now=now)
    if rem is not None and rem <= 0:
        return "miss"
    return "open"


def compute_streaks(outcomes_chrono: list[str]) -> tuple[int, int]:
    """Empty periods are absent from the list → they do not break the streak."""
    longest = 0
    run = 0
    for outcome in outcomes_chrono:
        if outcome == "completed":
            run += 1
            longest = max(longest, run)
        else:
            # miss or historical open → break longest run
            run = 0

    i = len(outcomes_chrono) - 1
    while i >= 0 and outcomes_chrono[i] == "open":
        i -= 1
    current = 0
    while i >= 0 and outcomes_chrono[i] == "completed":
        current += 1
        i -= 1
    return current, longest


def empty_daily(start: date, end: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    d = start
    while d <= end:
        out.append({"date": d.isoformat(), "issued": 0, "completed": 0, "failed": 0})
        d += timedelta(days=1)
    return out


async def build_stats(
    session: AsyncSession,
    *,
    days: int | None = 30,
    date_from: date | None = None,
    date_to: date | None = None,
    template_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    tz = resolve_tz(None)
    now = ensure_utc(now or datetime.now(UTC))
    assert now is not None
    start, end = resolve_range(days=days, date_from=date_from, date_to=date_to, tz=tz, now=now)
    lo, hi = range_bounds_utc(start, end, tz)

    daily_map = {row["date"]: row for row in empty_daily(start, end)}

    log_result = await session.exec(
        select(QuestChangeLog).where(
            col(QuestChangeLog.at) >= lo.replace(tzinfo=None),
            col(QuestChangeLog.at) < hi.replace(tzinfo=None),
            col(QuestChangeLog.kind).in_(
                list(ISSUED_KINDS | {COMPLETED_KIND, FAILED_KIND})
            ),
        )
    )
    # Distinct quest_id per kind per local day
    seen: set[tuple[str, str, int | None]] = set()
    for row in log_result.all():
        day = local_day(row.at, tz).isoformat()
        if day not in daily_map:
            continue
        kind = row.kind
        key = (day, kind, row.quest_id)
        if key in seen:
            continue
        seen.add(key)
        bucket = daily_map[day]
        if kind in ISSUED_KINDS:
            bucket["issued"] += 1
        elif kind == COMPLETED_KIND:
            bucket["completed"] += 1
        elif kind == FAILED_KIND:
            bucket["failed"] += 1

    tmpl_result = await session.exec(
        select(QuestTemplate).order_by(col(QuestTemplate.id))
    )
    templates = [
        {"id": int(t.id), "title": t.title, "enabled": bool(t.enabled)}
        for t in tmpl_result.all()
        if t.id is not None
    ]

    chosen_id = template_id
    if chosen_id is None and templates:
        enabled = [t for t in templates if t["enabled"]]
        chosen_id = (enabled or templates)[0]["id"]

    template_block: dict[str, Any] | None = None
    if chosen_id is not None:
        template_block = await _template_stats(
            session,
            template_id=int(chosen_id),
            start=start,
            end=end,
            now=now,
        )

    return {
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "daily": [daily_map[d.isoformat()] for d in _iter_days(start, end)],
        "templates": templates,
        "template": template_block,
    }


def _iter_days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


async def _template_stats(
    session: AsyncSession,
    *,
    template_id: int,
    start: date,
    end: date,
    now: datetime,
) -> dict[str, Any] | None:
    tmpl = await session.get(QuestTemplate, template_id)
    if tmpl is None or tmpl.id is None:
        return None

    result = await session.exec(
        select(Quest)
        .where(Quest.template_id == template_id)
        .where(col(Quest.period_key).is_not(None))
        .order_by(col(Quest.period_key))
    )
    instances = list(result.all())

    outcomes_all: list[str] = []
    for q in instances:
        outcomes_all.append(instance_outcome(q, now=now))
    current_streak, longest_streak = compute_streaks(outcomes_all)

    bars: list[dict[str, Any]] = []
    closed = 0
    total = 0
    for q in instances:
        key = q.period_key or ""
        if not key:
            continue
        try:
            pk = date.fromisoformat(key)
        except ValueError:
            continue
        if pk < start or pk > end:
            continue
        outcome = instance_outcome(q, now=now)
        status = q.status.value if hasattr(q.status, "value") else str(q.status)
        bars.append(
            {
                "period_key": key,
                "status": status,
                "outcome": outcome,
                "quest_id": q.id,
            }
        )
        total += 1
        if outcome == "completed":
            closed += 1

    close_rate = (closed / total) if total else 0.0
    return {
        "id": int(tmpl.id),
        "title": tmpl.title,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "closed": closed,
        "total": total,
        "close_rate": round(close_rate, 4),
        "bars": bars,
    }
