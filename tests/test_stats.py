"""Unit tests for stats aggregations + streaks."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.models import Quest, QuestChangeLog, QuestStatus, QuestTemplate, TemplateFreq
from quests.stats import build_stats, compute_streaks, instance_outcome


def test_compute_streaks_skips_gaps_in_list():
    # Gaps (no instance) are simply absent — list only has real instances.
    current, longest = compute_streaks(
        ["completed", "completed", "miss", "completed", "completed", "completed"]
    )
    assert longest == 3
    assert current == 3

    current, longest = compute_streaks(["completed", "completed", "open"])
    assert current == 2
    assert longest == 2

    current, longest = compute_streaks(["completed", "miss", "open"])
    assert current == 0
    assert longest == 1

    # Missed calendar day with no instance: only completed rows → streak continues
    current, longest = compute_streaks(["completed", "completed", "completed"])
    assert current == 3
    assert longest == 3


def test_instance_outcome_overdue_active_is_miss():
    now = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
    q = Quest(
        title="x",
        status=QuestStatus.active,
        deadline_at=datetime(2026, 8, 8, 12, 0),
        duration_seconds=3600,
    )
    assert instance_outcome(q, now=now) == "miss"
    q.status = QuestStatus.completed
    assert instance_outcome(q, now=now) == "completed"


def test_build_stats_daily_and_template():
    asyncio.run(_build_stats_flow())


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _build_stats_flow():
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            tmpl = QuestTemplate(
                title="Daily stretch",
                freq=TemplateFreq.daily,
                enabled=True,
                duration_seconds=3600,
            )
            session.add(tmpl)
            await session.commit()
            await session.refresh(tmpl)
            tid = int(tmpl.id)

            # Three periods: done, miss, done — gap day with no instance ignored for streak
            for key, status in (
                ("2026-08-01", QuestStatus.completed),
                ("2026-08-02", QuestStatus.failed),
                ("2026-08-04", QuestStatus.completed),
            ):
                session.add(
                    Quest(
                        title=f"inst {key}",
                        status=status,
                        template_id=tid,
                        period_key=key,
                        completed_at=datetime(2026, 8, 4, 10, 0)
                        if status == QuestStatus.completed
                        else None,
                    )
                )

            # Changelog in Moscow-friendly naive UTC
            session.add(
                QuestChangeLog(
                    at=datetime(2026, 8, 5, 10, 0),
                    kind="quest_created",
                    quest_id=1,
                    title="a",
                )
            )
            session.add(
                QuestChangeLog(
                    at=datetime(2026, 8, 5, 11, 0),
                    kind="quest_completed",
                    quest_id=1,
                    title="a",
                )
            )
            session.add(
                QuestChangeLog(
                    at=datetime(2026, 8, 5, 12, 0),
                    kind="quest_failed",
                    quest_id=2,
                    title="b",
                )
            )
            await session.commit()

            now = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)
            data = await build_stats(
                session,
                date_from=date(2026, 8, 1),
                date_to=date(2026, 8, 9),
                template_id=tid,
                now=now,
            )
            assert data["range"]["from"] == "2026-08-01"
            by_day = {d["date"]: d for d in data["daily"]}
            assert by_day["2026-08-05"]["issued"] == 1
            assert by_day["2026-08-05"]["completed"] == 1
            assert by_day["2026-08-05"]["failed"] == 1

            tmpl_stats = data["template"]
            assert tmpl_stats is not None
            assert tmpl_stats["id"] == tid
            # All-time streak: last completed after miss → current 1; longest 1
            assert tmpl_stats["current_streak"] == 1
            assert tmpl_stats["longest_streak"] == 1
            assert tmpl_stats["total"] == 3
            assert tmpl_stats["closed"] == 2
            assert len(tmpl_stats["bars"]) == 3
    finally:
        await engine.dispose()
