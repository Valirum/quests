"""Persist domain events to QuestChangeLog (skip noisy / non-durable kinds).

Prefer ``stage_event(session, ...)`` in the same transaction as the domain write.
A separate SessionLocal writer races with request handlers on SQLite.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal
from quests.models import QuestChangeLog, QuestChangeLogRead, utcnow

# Live toasts / maintenance that do not belong in durable history.
SKIP_KINDS = frozenset(
    {
        "startup",
        "step_progress",
        # Window-open notification; quest row unchanged.
        "quest_started",
    }
)


def should_persist(kind: str) -> bool:
    return bool(kind) and kind not in SKIP_KINDS


def stage_event(
    session: AsyncSession,
    *,
    kind: str,
    quest_id: int | None = None,
    title: str = "",
    detail: str = "",
    significance: Any = None,
    revision: int | None = None,
) -> QuestChangeLog | None:
    """Add a changelog row to ``session`` (no commit). Returns None if skipped."""
    kind = str(kind or "").strip()
    if not should_persist(kind):
        return None
    sig = str(significance).strip()[:16] if significance else None
    row = QuestChangeLog(
        at=utcnow(),
        kind=kind[:32],
        quest_id=quest_id,
        title=str(title or "")[:200],
        detail=str(detail or "")[:500],
        significance=sig or None,
        revision=revision,
    )
    session.add(row)
    return row



async def list_changes(
    *,
    limit: int = 100,
    quest_id: int | None = None,
    before_id: int | None = None,
) -> list[QuestChangeLogRead]:
    lim = max(1, min(500, int(limit)))
    async with SessionLocal() as session:
        stmt = select(QuestChangeLog).order_by(
            col(QuestChangeLog.at).desc(), col(QuestChangeLog.id).desc()
        )
        if quest_id is not None:
            stmt = stmt.where(QuestChangeLog.quest_id == int(quest_id))
        if before_id is not None:
            stmt = stmt.where(QuestChangeLog.id < int(before_id))
        stmt = stmt.limit(lim)
        rows = (await session.exec(stmt)).all()
    return [
        QuestChangeLogRead(
            id=int(r.id),
            at=r.at,
            kind=r.kind,
            quest_id=r.quest_id,
            title=r.title or "",
            detail=r.detail or "",
            significance=r.significance,
            revision=r.revision,
        )
        for r in rows
        if r.id is not None
    ]
