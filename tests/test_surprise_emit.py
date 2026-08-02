"""Tests for surprise emit helpers and materialize behaviour."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.models import (
    Quest,
    QuestTemplate,
    QuestTemplateStep,
    TemplateEmitMode,
    TemplateEmitOutcome,
    TemplateEmitRoll,
    TemplateFreq,
)
from quests.periodic import (
    _materialize,
    normalize_progress_range,
    parse_progress_range_text,
    pick_scheduled_at,
    resolve_progress_total,
    surprise_ready,
)


def test_normalize_progress_range_fixed_and_minmax():
    assert normalize_progress_range(progress_total=5) == (5, 5)
    assert normalize_progress_range(progress_min=3, progress_max=7) == (3, 7)
    assert normalize_progress_range(progress_min=7, progress_max=3) == (3, 7)
    assert normalize_progress_range(progress_min=4) == (4, 4)


def test_parse_progress_range_text():
    assert parse_progress_range_text("5") == (5, 5)
    assert parse_progress_range_text("5..10") == (5, 10)
    assert parse_progress_range_text("10-3") == (3, 10)
    assert parse_progress_range_text("") == (1, 1)


def test_resolve_progress_total_range():
    step = SimpleNamespace(progress_min=2, progress_max=5)
    rng = random.Random(0)
    values = {resolve_progress_total(step, rng=rng) for _ in range(40)}
    assert values <= {2, 3, 4, 5}
    assert len(values) >= 2


def test_pick_scheduled_at_within_window():
    local = datetime(2026, 8, 2, 8, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    rng = random.Random(1)
    picked = pick_scheduled_at(local, "10:00", "12:00", rng=rng)
    assert picked.tzinfo is not None
    assert picked.date() == local.date()
    assert picked.hour >= 10
    assert picked.hour <= 12


def test_surprise_ready_gate():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    waiting = TemplateEmitRoll(
        template_id=1,
        period_key="2026-08-02",
        outcome=TemplateEmitOutcome.scheduled,
        scheduled_at=datetime(2026, 8, 2, 13, 0),  # naive UTC
    )
    assert surprise_ready(waiting, now) is False
    waiting.scheduled_at = datetime(2026, 8, 2, 11, 0)
    assert surprise_ready(waiting, now) is True
    miss = TemplateEmitRoll(
        template_id=1,
        period_key="2026-08-02",
        outcome=TemplateEmitOutcome.miss,
        scheduled_at=None,
    )
    assert surprise_ready(miss, now) is False


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


def test_materialize_fixed_and_surprise_paths():
    asyncio.run(_materialize_cases())


async def _materialize_cases():
    engine, factory = await _session_factory()
    try:
        # Fixed template materializes immediately.
        async with factory() as session:
            fixed = QuestTemplate(
                title="Daily fixed",
                enabled=True,
                freq=TemplateFreq.daily,
                timezone="UTC",
                emit_mode=TemplateEmitMode.fixed,
                steps=[
                    QuestTemplateStep(
                        title="Do thing",
                        progress_min=1,
                        progress_max=1,
                        sort_order=0,
                    )
                ],
            )
            session.add(fixed)
            await session.commit()

        now = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
        async with factory() as session:
            created = await _materialize(session, now=now, rng=random.Random(0))
            assert len(created) == 1
            created_again = await _materialize(session, now=now, rng=random.Random(0))
            assert created_again == []

        # Surprise miss: chance 0 → no quest, one miss roll.
        async with factory() as session:
            surprise = QuestTemplate(
                title="Stretch",
                enabled=True,
                freq=TemplateFreq.daily,
                timezone="UTC",
                emit_mode=TemplateEmitMode.surprise,
                emit_chance=0.0,
                emit_window_start="09:00",
                emit_window_end="18:00",
                duration_seconds=900,
                steps=[
                    QuestTemplateStep(
                        title="Squats",
                        progress_min=5,
                        progress_max=10,
                        sort_order=0,
                    )
                ],
            )
            session.add(surprise)
            await session.commit()
            tid = surprise.id

        async with factory() as session:
            created = await _materialize(session, now=now, rng=random.Random(0))
            assert created == []
            rolls = list(
                (
                    await session.exec(
                        select(TemplateEmitRoll).where(TemplateEmitRoll.template_id == tid)
                    )
                ).all()
            )
            assert len(rolls) == 1
            assert rolls[0].outcome == TemplateEmitOutcome.miss
            # Second pass keeps miss, still no quest.
            assert await _materialize(session, now=now, rng=random.Random(0)) == []

        # Surprise hit: schedule in the past → materialize once with range total.
        async with factory() as session:
            hit = QuestTemplate(
                title="Walk",
                enabled=True,
                freq=TemplateFreq.daily,
                timezone="UTC",
                emit_mode=TemplateEmitMode.surprise,
                emit_chance=1.0,
                emit_window_start="00:00",
                emit_window_end="00:00",
                duration_seconds=600,
                steps=[
                    QuestTemplateStep(
                        title="Steps",
                        progress_min=3,
                        progress_max=3,
                        sort_order=0,
                    )
                ],
            )
            session.add(hit)
            await session.commit()
            hit_id = hit.id

        async with factory() as session:
            created = await _materialize(session, now=now, rng=random.Random(42))
            assert len(created) == 1
            quest = (
                await session.exec(select(Quest).where(Quest.id == created[0]))
            ).first()
            assert quest is not None
            assert quest.template_id == hit_id
            assert quest.duration_seconds == 600
            assert quest.deadline_at is not None
            assert quest.steps[0].progress_total == 3
            roll = (
                await session.exec(
                    select(TemplateEmitRoll).where(TemplateEmitRoll.template_id == hit_id)
                )
            ).first()
            assert roll is not None
            assert roll.outcome == TemplateEmitOutcome.materialized
            assert await _materialize(session, now=now, rng=random.Random(42)) == []

        # Surprise scheduled in the future → wait, then materialize.
        async with factory() as session:
            future = QuestTemplate(
                title="Later",
                enabled=True,
                freq=TemplateFreq.daily,
                timezone="UTC",
                emit_mode=TemplateEmitMode.surprise,
                emit_chance=1.0,
                emit_window_start="15:00",
                emit_window_end="15:00",
                duration_seconds=120,
                steps=[
                    QuestTemplateStep(
                        title="Later step",
                        progress_min=2,
                        progress_max=8,
                        sort_order=0,
                    )
                ],
            )
            session.add(future)
            await session.commit()
            future_id = future.id

        morning = datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc)
        async with factory() as session:
            assert await _materialize(session, now=morning, rng=random.Random(1)) == []
            roll = (
                await session.exec(
                    select(TemplateEmitRoll).where(
                        TemplateEmitRoll.template_id == future_id
                    )
                )
            ).first()
            assert roll is not None
            assert roll.outcome == TemplateEmitOutcome.scheduled
            assert roll.scheduled_at is not None

        afternoon = datetime(2026, 8, 2, 15, 1, tzinfo=timezone.utc)
        async with factory() as session:
            created = await _materialize(
                session, now=afternoon, rng=random.Random(1)
            )
            assert len(created) == 1
            quest = (
                await session.exec(select(Quest).where(Quest.id == created[0]))
            ).first()
            assert quest is not None
            total = quest.steps[0].progress_total
            assert 2 <= total <= 8
    finally:
        await engine.dispose()
