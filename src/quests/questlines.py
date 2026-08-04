"""Questline helpers (validate + sync member categories)."""

from __future__ import annotations

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import validate_category_id
from quests.models import Quest, QuestLine, QuestTemplate


async def get_questline(
    session: AsyncSession, questline_id: int
) -> QuestLine | None:
    return (
        await session.exec(select(QuestLine).where(QuestLine.id == int(questline_id)))
    ).first()


async def validate_questline_id(
    session: AsyncSession, questline_id: int | None
) -> int | None:
    if questline_id is None:
        return None
    row = await get_questline(session, int(questline_id))
    if row is None:
        return None
    return int(row.id)  # type: ignore[arg-type]


async def apply_questline_membership(
    session: AsyncSession, obj: Any, questline_id: int | None
) -> None:
    """Set questline_id and force category_id from the line (or leave category if unlinked)."""
    qid = await validate_questline_id(session, questline_id)
    obj.questline_id = qid
    if qid is None:
        return
    line = await get_questline(session, qid)
    if line is None:
        obj.questline_id = None
        return
    obj.category_id = await validate_category_id(session, line.category_id)


async def apply_questline_to_quest(
    session: AsyncSession, quest: Quest, questline_id: int | None
) -> None:
    await apply_questline_membership(session, quest, questline_id)


async def apply_questline_to_template(
    session: AsyncSession, tmpl: QuestTemplate, questline_id: int | None
) -> None:
    await apply_questline_membership(session, tmpl, questline_id)


async def sync_member_categories(
    session: AsyncSession, line: QuestLine
) -> int:
    """Force all member quests/templates to the line's category_id. Returns updated count."""
    cat_id = await validate_category_id(session, line.category_id)
    line.category_id = cat_id
    updated = 0
    members = list(
        (
            await session.exec(select(Quest).where(Quest.questline_id == line.id))
        ).all()
    )
    for q in members:
        q.category_id = cat_id
        session.add(q)
        updated += 1
    tmpls = list(
        (
            await session.exec(
                select(QuestTemplate).where(QuestTemplate.questline_id == line.id)
            )
        ).all()
    )
    for t in tmpls:
        t.category_id = cat_id
        session.add(t)
        updated += 1
    return updated
