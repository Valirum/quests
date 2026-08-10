"""Mark overdue active quests as delayed (failed stays manual)."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal, quest_load_options
from quests.emit import deliver_staged, stage_quest_diff
from quests.hero import apply_quest_status_rewards
from quests.models import Quest, QuestStatus, utcnow
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
        .options(*quest_load_options())
    )
    overdue = list(result.all())
    if not overdue:
        return []

    staged: list = []
    delayed_ids: list[int] = []
    for quest in overdue:
        before = quest_to_read(quest)
        quest.status = QuestStatus.delayed
        quest.updated_at = utcnow()
        session.add(quest)
        await apply_quest_status_rewards(session, quest, new_status=QuestStatus.delayed)
        after = quest_to_read(quest)
        delayed_ids.append(after.id)
        staged.extend(
            stage_quest_diff(session, before, after, quiet=False, source="system")
        )

    await session.commit()
    await deliver_staged(staged)
    return delayed_ids


async def expire_overdue_quests(session: AsyncSession | None = None) -> list[int]:
    """Delay active quests whose deadline has passed. Returns delayed quest ids."""
    if session is not None:
        return await _expire(session)
    async with SessionLocal() as session:
        return await _expire(session)
