"""Hero sheet: XP, momentum, attributes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.hero import (
    apply_attribute_progress,
    apply_quest_status_rewards,
    decay_momentum,
    ensure_hero_sheet,
    hero_to_read,
    normalize_reward_attrs,
    parse_reward_attrs,
    progress_to_next,
)
from quests.models import (
    HeroAttribute,
    HeroSheet,
    MetricLedger,
    Quest,
    QuestSignificance,
    QuestStatus,
    QuestStep,
)


def test_progress_to_next_grows():
    assert progress_to_next(0) == 10
    assert progress_to_next(1) == 15
    assert progress_to_next(2) == 20
    assert progress_to_next(10) > progress_to_next(5)


def test_parse_and_normalize_reward_attrs():
    assert parse_reward_attrs('{"int": 2, "wis": 1, "nope": 9}') == {
        "int": 2,
        "wis": 1,
    }
    assert normalize_reward_attrs('{"str":1}') == '{"str": 1}'
    assert normalize_reward_attrs("{}") is None
    assert normalize_reward_attrs("not-json") is None


def test_attribute_rank_up_with_remainder():
    attr = HeroAttribute(attr_id="str", rank=0, progress=0)
    # need(0)=10; grant 25 → rank 2, progress 0 (10+15=25)
    apply_attribute_progress(attr, 25)
    assert attr.rank == 2
    assert attr.progress == 0
    # need(2)=20; grant 25 → rank 3, progress 5
    apply_attribute_progress(attr, 25)
    assert attr.rank == 3
    assert attr.progress == 5


def test_hero_rewards_and_decay():
    asyncio.run(_hero_flow())


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _hero_flow():
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            sheet = await ensure_hero_sheet(session)
            await session.commit()
            assert sheet.xp == 0
            assert sheet.momentum == 50

        async with factory() as session:
            quest = Quest(
                title="Учёба",
                status=QuestStatus.active,
                significance=QuestSignificance.common,
                reward_attrs='{"int":1,"wis":1}',
                steps=[
                    QuestStep(
                        title="Глава",
                        progress_current=0,
                        progress_total=1,
                        sort_order=0,
                    )
                ],
            )
            session.add(quest)
            await session.commit()
            await session.refresh(quest)
            qid = int(quest.id)

            applied = await apply_quest_status_rewards(
                session, quest, new_status=QuestStatus.completed
            )
            await session.commit()
            assert applied is True

            sheet = await session.get(HeroSheet, 1)
            assert sheet is not None
            assert sheet.xp == 20
            assert sheet.momentum == 62  # 50+12

            attrs = {
                a.attr_id: a
                for a in (await session.exec(select(HeroAttribute))).all()
            }
            assert attrs["int"].progress + attrs["wis"].progress == 8
            # Idempotent
            assert (
                await apply_quest_status_rewards(
                    session, quest, new_status=QuestStatus.completed
                )
                is False
            )
            await session.commit()
            sheet2 = await session.get(HeroSheet, 1)
            assert sheet2 is not None
            assert sheet2.xp == 20

            quest.status = QuestStatus.failed
            session.add(quest)
            await apply_quest_status_rewards(
                session, quest, new_status=QuestStatus.failed
            )
            await session.commit()
            sheet3 = await session.get(HeroSheet, 1)
            assert sheet3 is not None
            assert sheet3.momentum == 42  # 62-20

        # Decay: 3 idle hours from stamped updated_at
        async with factory() as session:
            sheet = await ensure_hero_sheet(session)
            base = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
            sheet.momentum = 50
            sheet.momentum_updated_at = base.replace(tzinfo=None)
            session.add(sheet)
            await session.commit()

            decayed = await decay_momentum(
                session, now=base + timedelta(hours=3, minutes=10)
            )
            await session.commit()
            assert decayed == 3
            sheet = await session.get(HeroSheet, 1)
            assert sheet is not None
            assert sheet.momentum == 47

            read = await hero_to_read(session)
            assert read.xp >= 20
            assert len(read.attributes) == 6
            assert any(r.kind == "momentum" for r in read.recent)
            assert any(r.quest_id == qid for r in read.recent)

            ledgers = list((await session.exec(select(MetricLedger))).all())
            assert ledgers
    finally:
        await engine.dispose()
