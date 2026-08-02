"""Mark overdue active quests as failed (delayed is user-set, left alone)."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal, quest_load_options
from quests.events import hub
from quests.models import Quest, QuestStatus, utcnow
from quests.notify import quest_change_events
from quests.serializers import quest_to_read
from quests.timeutil import to_db_utc


async def _expire(session: AsyncSession) -> list[int]:
    now = to_db_utc(utcnow())
    assert now is not None
    result = await session.exec(
        select(Quest)
        .where(Quest.status == QuestStatus.active)
        .where(col(Quest.deadline_at).is_not(None))
        .where(col(Quest.deadline_at) <= now)
        .options(quest_load_options())
    )
    overdue = list(result.all())
    if not overdue:
        return []

    pairs: list[tuple] = []
    for quest in overdue:
        before = quest_to_read(quest)
        quest.status = QuestStatus.failed
        quest.updated_at = utcnow()
        session.add(quest)
        pairs.append((before, quest))

    await session.commit()

    failed_ids: list[int] = []
    for before, quest in pairs:
        await session.refresh(quest)
        after = quest_to_read(quest)
        failed_ids.append(after.id)
        for ev in quest_change_events(before, after):
            await hub.publish(
                ev["kind"],
                quest_id=after.id,
                title=ev.get("title", after.title),
                description=ev.get("description", after.description or ""),
                detail=ev.get("detail", ""),
                sound=ev.get("sound"),
                toast=ev.get("toast", True),
                step_title=ev.get("step_title"),
                significance=ev.get("significance"),
            )
    return failed_ids


async def expire_overdue_quests(session: AsyncSession | None = None) -> list[int]:
    """Fail active quests whose deadline has passed. Returns failed quest ids."""
    if session is not None:
        return await _expire(session)
    async with SessionLocal() as session:
        return await _expire(session)
