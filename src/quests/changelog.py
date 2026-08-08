"""Persist domain events to QuestChangeLog (skip noisy / non-durable kinds)."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import col, select

from quests.db import SessionLocal
from quests.models import QuestChangeLog, QuestChangeLogRead, utcnow

log = logging.getLogger("quests.changelog")

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


async def persist_event(payload: dict[str, Any]) -> None:
    """Write one hub event to SQLite. Safe to fire-and-forget."""
    kind = str(payload.get("kind") or "").strip()
    if not should_persist(kind):
        return
    title = str(payload.get("title") or "")[:200]
    detail = str(payload.get("detail") or "")[:500]
    sig = payload.get("significance")
    significance = str(sig).strip()[:16] if sig else None
    qid = payload.get("quest_id")
    try:
        quest_id = int(qid) if qid is not None else None
    except (TypeError, ValueError):
        quest_id = None
    rev = payload.get("revision")
    try:
        revision = int(rev) if rev is not None else None
    except (TypeError, ValueError):
        revision = None

    try:
        async with SessionLocal() as session:
            session.add(
                QuestChangeLog(
                    at=utcnow(),
                    kind=kind[:32],
                    quest_id=quest_id,
                    title=title,
                    detail=detail,
                    significance=significance or None,
                    revision=revision,
                )
            )
            await session.commit()
    except Exception:
        log.exception("failed to persist quest change log kind=%s", kind)


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
