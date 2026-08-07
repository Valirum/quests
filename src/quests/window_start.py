"""Publish quest_started when (deadline − duration) is crossed."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal, quest_load_options
from quests.events import hub
from quests.models import Quest, QuestStatus
from quests.notify import significance_value
from quests.serializers import quest_to_read
from quests.timeutil import is_in_urgent_window, remaining_seconds

# In-process dedup: fire once per quest while it stays in the window.
_notified: set[int] = set()
_seeded = False


async def _active_in_window(session: AsyncSession) -> list[Quest]:
    result = await session.exec(
        select(Quest)
        .where(Quest.status == QuestStatus.active)
        .where(col(Quest.deadline_at).is_not(None))
        .where(col(Quest.duration_seconds).is_not(None))
        .options(*quest_load_options())
    )
    out: list[Quest] = []
    for quest in result.all():
        rem = remaining_seconds(quest.deadline_at)
        # Only the open window before expire (overdue → quest_delayed separately).
        if rem is not None and rem <= 0:
            continue
        if is_in_urgent_window(quest.deadline_at, quest.duration_seconds):
            out.append(quest)
    return out


async def notify_window_starts(session: AsyncSession | None = None) -> list[int]:
    """Emit ``quest_started`` once when the urgent window opens.

    On first call after process start, seed currently-open windows without
    toasting (same idea as the Telegram bot loop).
    """
    global _seeded

    async def _run(sess: AsyncSession) -> list[int]:
        global _seeded
        in_window = await _active_in_window(sess)
        live_ids = {int(q.id) for q in in_window if q.id is not None}

        # Drop ids that left the window / are no longer active.
        _notified.intersection_update(live_ids)

        if not _seeded:
            _notified.update(live_ids)
            _seeded = True
            return []

        fired: list[int] = []
        for quest in in_window:
            qid = int(quest.id) if quest.id is not None else None
            if qid is None or qid in _notified:
                continue
            _notified.add(qid)
            read = quest_to_read(quest)
            await hub.publish(
                "quest_started",
                quest_id=qid,
                title=read.title,
                description=read.description or "",
                detail=read.progress_label,
                sound="quest_started",
                toast=True,
                significance=significance_value(read),
            )
            fired.append(qid)
        return fired

    if session is not None:
        return await _run(session)
    async with SessionLocal() as sess:
        return await _run(sess)
