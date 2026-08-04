"""Questline CRUD, category force, sync, unlink."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import ensure_categories
from quests.models import Quest, QuestLine, QuestStatus, QuestStep
from quests.questlines import apply_questline_to_quest, sync_member_categories
from quests.serializers import quest_to_read


def test_questlines_flow():
    asyncio.run(_flow())


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _flow():
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            cats = await ensure_categories(session)
            await session.commit()
            by_slug = {c.slug: c for c in cats}
            work_id = int(by_slug["work"].id)
            health_id = int(by_slug["health"].id)

            line = QuestLine(
                title="Проект Quests",
                description="Долгая линия",
                category_id=work_id,
                color="#5a8a9a",
                icon="flag",
            )
            session.add(line)
            await session.commit()
            line_id = int(line.id)

        async with factory() as session:
            quest = Quest(
                title="MVP",
                status=QuestStatus.active,
                category_id=health_id,  # will be overwritten
                steps=[
                    QuestStep(
                        title="Сделать",
                        progress_current=0,
                        progress_total=1,
                        sort_order=0,
                    )
                ],
            )
            session.add(quest)
            await session.flush()
            await apply_questline_to_quest(session, quest, line_id)
            session.add(quest)
            await session.commit()
            qid = int(quest.id)

            loaded = (
                await session.exec(
                    select(Quest)
                    .where(Quest.id == qid)
                    .options(
                        selectinload(Quest.steps),
                        selectinload(Quest.category),
                        selectinload(Quest.questline),
                    )
                )
            ).first()
            assert loaded is not None
            assert loaded.questline_id == line_id
            assert loaded.category_id == work_id
            read = quest_to_read(loaded)
            assert read.questline_title == "Проект Quests"
            assert read.questline_color == "#5a8a9a"
            assert read.questline_icon == "flag"
            assert read.category_slug == "work"

            line_row = (
                await session.exec(select(QuestLine).where(QuestLine.id == line_id))
            ).first()
            assert line_row is not None
            line_row.category_id = health_id
            await sync_member_categories(session, line_row)
            session.add(line_row)
            await session.commit()

            loaded2 = (
                await session.exec(select(Quest).where(Quest.id == qid))
            ).first()
            assert loaded2 is not None
            assert loaded2.category_id == health_id

            # Unlink on delete semantics
            loaded2.questline_id = None
            session.add(loaded2)
            await session.delete(line_row)
            await session.commit()

            leftover = (
                await session.exec(select(Quest).where(Quest.id == qid))
            ).first()
            assert leftover is not None
            assert leftover.questline_id is None
            assert leftover.category_id == health_id  # kept
            assert (await session.exec(select(QuestLine))).first() is None
    finally:
        await engine.dispose()
