"""Hero sheet: XP, momentum (impulse), and D&D-like attributes."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal
from quests.models import (
    ATTR_LABEL_RU,
    HeroAttribute,
    HeroAttributeId,
    HeroAttributeRead,
    HeroSheet,
    HeroSheetRead,
    MetricLedger,
    MetricLedgerRead,
    Quest,
    QuestSignificance,
    QuestStatus,
    utcnow,
)
from quests.timeutil import ensure_utc, to_db_utc

SHEET_ID = 1
MOMENTUM_MIN = 0
MOMENTUM_MAX = 100
MOMENTUM_DEFAULT = 50

# Tunable live — start simple.
ATTR_NEED_BASE = 10
ATTR_NEED_K = 5
XP_ON_COMPLETE = 20
ATTR_PROGRESS_POOL = 8
MOMENTUM_ON_COMPLETE = 12
MOMENTUM_ON_FAIL = -20
MOMENTUM_ON_DELAYED = -2

SIGNIFICANCE_MULT: dict[str, float] = {
    QuestSignificance.common.value: 1.0,
    QuestSignificance.uncommon.value: 1.25,
    QuestSignificance.epic.value: 1.75,
    QuestSignificance.legendary.value: 2.5,
}

ATTR_ORDER = [a.value for a in HeroAttributeId]


def progress_to_next(rank: int) -> int:
    """Progress units needed to go from `rank` to rank+1."""
    r = max(0, int(rank))
    return max(1, ATTR_NEED_BASE + ATTR_NEED_K * r)


def significance_mult(raw: Any) -> float:
    key = str(getattr(raw, "value", raw) or "common")
    return SIGNIFICANCE_MULT.get(key, 1.0)


def parse_reward_attrs(raw: str | None) -> dict[str, int]:
    """Parse JSON weights; unknown keys dropped; non-positive ignored."""
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, int] = {}
    known = set(ATTR_ORDER)
    for key, val in data.items():
        kid = str(key).strip().lower()
        if kid not in known:
            continue
        try:
            w = int(val)
        except (TypeError, ValueError):
            continue
        if w > 0:
            out[kid] = w
    return out


def normalize_reward_attrs(raw: str | None) -> str | None:
    weights = parse_reward_attrs(raw)
    if not weights:
        return None
    return json.dumps(weights, ensure_ascii=False, sort_keys=True)


def _aware(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def ensure_hero_sheet(session: AsyncSession) -> HeroSheet:
    sheet = await session.get(HeroSheet, SHEET_ID)
    if sheet is None:
        sheet = HeroSheet(
            id=SHEET_ID,
            xp=0,
            momentum=MOMENTUM_DEFAULT,
            momentum_updated_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(sheet)
        await session.flush()

    existing = {
        row.attr_id: row
        for row in (
            await session.exec(select(HeroAttribute))
        ).all()
    }
    for attr_id in ATTR_ORDER:
        if attr_id not in existing:
            session.add(
                HeroAttribute(
                    attr_id=attr_id,
                    rank=0,
                    progress=0,
                    updated_at=utcnow(),
                )
            )
    await session.flush()
    return sheet


async def _ledger_exists(
    session: AsyncSession, *, quest_id: int, reason: str
) -> bool:
    result = await session.exec(
        select(MetricLedger.id)
        .where(MetricLedger.quest_id == quest_id)
        .where(MetricLedger.reason == reason)
        .limit(1)
    )
    return result.first() is not None


async def _add_ledger(
    session: AsyncSession,
    *,
    kind: str,
    delta: int,
    balance_after: int,
    reason: str,
    quest_id: int | None = None,
    attr_id: str | None = None,
    flavor: str | None = None,
) -> MetricLedger:
    row = MetricLedger(
        at=utcnow(),
        kind=kind,
        attr_id=attr_id,
        delta=int(delta),
        balance_after=int(balance_after),
        quest_id=quest_id,
        reason=reason,
        flavor=flavor,
    )
    session.add(row)
    return row


def _clamp_momentum(value: int) -> int:
    return max(MOMENTUM_MIN, min(MOMENTUM_MAX, int(value)))


async def _apply_momentum(
    session: AsyncSession,
    sheet: HeroSheet,
    delta: int,
    *,
    reason: str,
    quest_id: int | None,
    flavor: str | None = None,
) -> None:
    if delta == 0:
        return
    sheet.momentum = _clamp_momentum(sheet.momentum + delta)
    sheet.momentum_updated_at = utcnow()
    sheet.updated_at = utcnow()
    session.add(sheet)
    await _add_ledger(
        session,
        kind="momentum",
        delta=delta,
        balance_after=sheet.momentum,
        reason=reason,
        quest_id=quest_id,
        flavor=flavor,
    )


async def _apply_xp(
    session: AsyncSession,
    sheet: HeroSheet,
    delta: int,
    *,
    reason: str,
    quest_id: int | None,
    flavor: str | None = None,
) -> None:
    if delta <= 0:
        return
    sheet.xp = max(0, int(sheet.xp) + int(delta))
    sheet.updated_at = utcnow()
    session.add(sheet)
    await _add_ledger(
        session,
        kind="xp",
        delta=delta,
        balance_after=sheet.xp,
        reason=reason,
        quest_id=quest_id,
        flavor=flavor,
    )


async def _get_attr(session: AsyncSession, attr_id: str) -> HeroAttribute:
    result = await session.exec(
        select(HeroAttribute).where(HeroAttribute.attr_id == attr_id).limit(1)
    )
    row = result.first()
    if row is None:
        row = HeroAttribute(attr_id=attr_id, rank=0, progress=0, updated_at=utcnow())
        session.add(row)
        await session.flush()
    return row


def apply_attribute_progress(attr: HeroAttribute, gained: int) -> list[tuple[int, int]]:
    """Add progress; return list of (delta_chunk, balance_after_progress) ledger hints.
    Rank-ups happen in place; one ledger line per call is enough (balance = progress after).
    """
    gained = max(0, int(gained))
    if gained <= 0:
        return []
    attr.progress = int(attr.progress) + gained
    while attr.progress >= progress_to_next(attr.rank):
        need = progress_to_next(attr.rank)
        attr.progress -= need
        attr.rank += 1
    attr.updated_at = utcnow()
    return [(gained, attr.progress)]


async def _apply_attrs(
    session: AsyncSession,
    *,
    weights: dict[str, int],
    pool: int,
    reason: str,
    quest_id: int,
    flavor: str | None = None,
) -> None:
    if pool <= 0 or not weights:
        return
    total_w = sum(weights.values())
    if total_w <= 0:
        return
    # Largest-remainder distribution so sum == pool.
    parts: list[tuple[str, float]] = []
    for attr_id, w in weights.items():
        parts.append((attr_id, pool * w / total_w))
    floors = {a: int(math.floor(v)) for a, v in parts}
    rem = pool - sum(floors.values())
    by_frac = sorted(parts, key=lambda x: x[1] - math.floor(x[1]), reverse=True)
    for i in range(rem):
        floors[by_frac[i % len(by_frac)][0]] += 1

    for attr_id, grant in floors.items():
        if grant <= 0:
            continue
        attr = await _get_attr(session, attr_id)
        apply_attribute_progress(attr, grant)
        session.add(attr)
        await _add_ledger(
            session,
            kind="attr",
            delta=grant,
            balance_after=attr.progress,
            reason=f"{reason}:{attr_id}",
            quest_id=quest_id,
            attr_id=attr_id,
            flavor=flavor,
        )


async def apply_quest_status_rewards(
    session: AsyncSession,
    quest: Quest,
    *,
    new_status: QuestStatus | str,
) -> bool:
    """Apply idempotent rewards for a status transition. True if anything applied."""
    status = (
        new_status
        if isinstance(new_status, QuestStatus)
        else QuestStatus(str(new_status))
    )
    qid = int(quest.id) if quest.id is not None else None
    if qid is None:
        return False

    if status == QuestStatus.completed:
        reason = "quest_completed"
    elif status == QuestStatus.failed:
        reason = "quest_failed"
    elif status == QuestStatus.delayed:
        reason = "quest_delayed"
    else:
        return False

    if await _ledger_exists(session, quest_id=qid, reason=reason):
        return False

    sheet = await ensure_hero_sheet(session)
    mult = significance_mult(quest.significance)
    title = quest.title or f"#{qid}"

    if status == QuestStatus.completed:
        xp = max(1, int(round(XP_ON_COMPLETE * mult)))
        mom = max(1, int(round(MOMENTUM_ON_COMPLETE * mult)))
        await _apply_xp(
            session,
            sheet,
            xp,
            reason=reason,
            quest_id=qid,
            flavor=f"+{xp} XP · {title}",
        )
        await _apply_momentum(
            session,
            sheet,
            mom,
            reason=f"{reason}:momentum",
            quest_id=qid,
            flavor=f"Импульс +{mom}",
        )
        weights = parse_reward_attrs(quest.reward_attrs)
        pool = max(1, int(round(ATTR_PROGRESS_POOL * mult)))
        await _apply_attrs(
            session,
            weights=weights,
            pool=pool,
            reason=reason,
            quest_id=qid,
            flavor=title,
        )
        # Marker row so re-complete is idempotent even if only xp line used shared reason.
        # XP already used reason=quest_completed; attrs use quest_completed:attr.
        return True

    if status == QuestStatus.failed:
        mom = min(-1, int(round(MOMENTUM_ON_FAIL * mult)))
        await _apply_momentum(
            session,
            sheet,
            mom,
            reason=reason,
            quest_id=qid,
            flavor=f"Импульс {mom} · провал: {title}",
        )
        return True

    # delayed
    mom = MOMENTUM_ON_DELAYED
    await _apply_momentum(
        session,
        sheet,
        mom,
        reason=reason,
        quest_id=qid,
        flavor=f"Импульс {mom} · отсрочка: {title}",
    )
    return True


async def decay_momentum(
    session: AsyncSession | None = None,
    *,
    now: datetime | None = None,
) -> int:
    """Subtract 1 momentum per whole idle hour. Returns points decayed."""

    async def _run(s: AsyncSession) -> int:
        sheet = await ensure_hero_sheet(s)
        now_utc = _aware(now or datetime.now(timezone.utc))
        updated = _aware(sheet.momentum_updated_at)
        hours = int((now_utc - updated).total_seconds() // 3600)
        if hours <= 0 or sheet.momentum <= 0:
            return 0
        delta = -min(hours, sheet.momentum)
        if delta == 0:
            return 0
        sheet.momentum = _clamp_momentum(sheet.momentum + delta)
        # Preserve fractional hour.
        sheet.momentum_updated_at = to_db_utc(updated + timedelta(hours=hours))
        sheet.updated_at = utcnow()
        s.add(sheet)
        await _add_ledger(
            s,
            kind="momentum",
            delta=delta,
            balance_after=sheet.momentum,
            reason="momentum_decay",
            quest_id=None,
            flavor=f"Бездействие (−{abs(delta)}/ч)",
        )
        await s.commit()
        return abs(delta)

    if session is not None:
        # Caller owns commit when nested; still commit-safe if they commit later.
        sheet = await ensure_hero_sheet(session)
        now_utc = _aware(now or datetime.now(timezone.utc))
        updated = _aware(sheet.momentum_updated_at)
        hours = int((now_utc - updated).total_seconds() // 3600)
        if hours <= 0 or sheet.momentum <= 0:
            return 0
        delta = -min(hours, sheet.momentum)
        if delta == 0:
            return 0
        sheet.momentum = _clamp_momentum(sheet.momentum + delta)
        sheet.momentum_updated_at = to_db_utc(updated + timedelta(hours=hours))
        sheet.updated_at = utcnow()
        session.add(sheet)
        await _add_ledger(
            session,
            kind="momentum",
            delta=delta,
            balance_after=sheet.momentum,
            reason="momentum_decay",
            quest_id=None,
            flavor=f"Бездействие (−{abs(delta)}/ч)",
        )
        return abs(delta)

    async with SessionLocal() as s:
        return await _run(s)


async def hero_to_read(
    session: AsyncSession, *, recent_limit: int = 30
) -> HeroSheetRead:
    sheet = await ensure_hero_sheet(session)
    attrs = list((await session.exec(select(HeroAttribute))).all())
    by_id = {a.attr_id: a for a in attrs}
    attr_reads: list[HeroAttributeRead] = []
    for attr_id in ATTR_ORDER:
        row = by_id.get(attr_id)
        if row is None:
            attr_reads.append(
                HeroAttributeRead(
                    attr_id=attr_id,
                    label=ATTR_LABEL_RU.get(attr_id, attr_id),
                    rank=0,
                    progress=0,
                    progress_to_next=progress_to_next(0),
                )
            )
            continue
        attr_reads.append(
            HeroAttributeRead(
                attr_id=row.attr_id,
                label=ATTR_LABEL_RU.get(row.attr_id, row.attr_id),
                rank=int(row.rank),
                progress=int(row.progress),
                progress_to_next=progress_to_next(row.rank),
            )
        )

    recent_rows = list(
        (
            await session.exec(
                select(MetricLedger)
                .order_by(col(MetricLedger.at).desc(), col(MetricLedger.id).desc())
                .limit(max(1, recent_limit))
            )
        ).all()
    )
    recent = [
        MetricLedgerRead(
            id=int(r.id),  # type: ignore[arg-type]
            at=r.at,
            kind=r.kind,
            attr_id=r.attr_id,
            delta=r.delta,
            balance_after=r.balance_after,
            quest_id=r.quest_id,
            reason=r.reason,
            flavor=r.flavor,
        )
        for r in recent_rows
    ]
    return HeroSheetRead(
        xp=int(sheet.xp),
        momentum=int(sheet.momentum),
        momentum_updated_at=sheet.momentum_updated_at,
        updated_at=sheet.updated_at,
        attributes=attr_reads,
        recent=recent,
    )
