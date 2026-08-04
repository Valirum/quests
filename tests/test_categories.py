"""Quest category seed, assign, and template materialize copy."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import ensure_categories
from quests.models import (
    CATEGORY_SEED,
    Quest,
    QuestCategory,
    QuestStatus,
    QuestStep,
    QuestTemplate,
    QuestTemplateStep,
    TemplateFreq,
)
from quests.periodic import _materialize
from quests.serializers import quest_to_read


def test_category_seed_constant():
    slugs = [s for s, _, _, _ in CATEGORY_SEED]
    assert slugs == ["work", "routine", "health", "study", "fun"]
    labels = [lab for _, lab, _, _ in CATEGORY_SEED]
    assert labels == ["Работа", "Рутина", "Здоровье", "Учёба", "Развлечения"]
    colors = [c for _, _, _, c in CATEGORY_SEED]
    assert all(c.startswith("#") and len(c) == 7 for c in colors)


def test_categories_flow():
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
            rows = await ensure_categories(session)
            await session.commit()
            assert len(rows) == 5
            by_slug = {r.slug: r for r in rows}
            assert by_slug["work"].label == "Работа"
            assert by_slug["work"].color == "#5a8a9a"
            # Idempotent
            again = await ensure_categories(session)
            await session.commit()
            assert len(again) == 5
            work_id = int(by_slug["work"].id)

        async with factory() as session:
            quest = Quest(
                title="Отчёт",
                status=QuestStatus.active,
                category_id=work_id,
                steps=[
                    QuestStep(
                        title="Черновик",
                        progress_current=0,
                        progress_total=1,
                        sort_order=0,
                    )
                ],
            )
            session.add(quest)
            await session.commit()
            qid = int(quest.id)

            loaded = (
                await session.exec(
                    select(Quest)
                    .where(Quest.id == qid)
                    .options(selectinload(Quest.steps), selectinload(Quest.category))
                )
            ).first()
            assert loaded is not None
            read = quest_to_read(loaded)
            assert read.category_id == work_id
            assert read.category_slug == "work"
            assert read.category_label == "Работа"
            assert read.category_color == "#5a8a9a"

            tmpl = QuestTemplate(
                title="Утренняя зарядка",
                enabled=True,
                freq=TemplateFreq.daily,
                timezone="UTC",
                category_id=int(by_slug["health"].id),
                steps=[
                    QuestTemplateStep(
                        title="Разминка",
                        progress_min=1,
                        progress_max=1,
                        sort_order=0,
                    )
                ],
            )
            session.add(tmpl)
            await session.commit()
            health_id = int(by_slug["health"].id)

        now = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)
        async with factory() as session:
            created = await _materialize(session, now=now)
            assert len(created) == 1
            inst = (
                await session.exec(
                    select(Quest)
                    .where(Quest.id == created[0])
                    .options(selectinload(Quest.steps), selectinload(Quest.category))
                )
            ).first()
            assert inst is not None
            assert inst.category_id == health_id
            read = quest_to_read(inst)
            assert read.category_slug == "health"
            assert read.category_label == "Здоровье"
            assert read.category_color == "#7a9e3a"

            cats = list((await session.exec(select(QuestCategory))).all())
            assert len(cats) == 5
    finally:
        await engine.dispose()
