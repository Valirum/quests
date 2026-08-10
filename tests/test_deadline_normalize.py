"""Shared deadline / duration auto-fill semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quests.timeutil import (
    DEFAULT_DURATION_SECONDS,
    auto_duration_seconds,
    normalize_quest_deadline,
)


def test_auto_duration_caps_at_24h() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    deadline = now + timedelta(days=10)
    assert auto_duration_seconds(deadline, now) == DEFAULT_DURATION_SECONDS


def test_auto_duration_short_deadline() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    deadline = now + timedelta(hours=3)
    assert auto_duration_seconds(deadline, now) == 3 * 3600


def test_normalize_create_and_update_same_anchor() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    deadline = now + timedelta(days=2)
    d1, dur1 = normalize_quest_deadline(
        deadline_at=deadline,
        duration_seconds=None,
        duration_explicit=False,
        now=now,
    )
    d2, dur2 = normalize_quest_deadline(
        deadline_at=deadline,
        duration_seconds=None,
        duration_explicit=False,
        now=now,
    )
    assert d1 == d2
    assert dur1 == dur2 == DEFAULT_DURATION_SECONDS


def test_normalize_explicit_duration() -> None:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    deadline = now + timedelta(days=2)
    _, dur = normalize_quest_deadline(
        deadline_at=deadline,
        duration_seconds=90,
        duration_explicit=True,
        now=now,
    )
    assert dur == 90


def test_normalize_clears_without_deadline() -> None:
    d, dur = normalize_quest_deadline(
        deadline_at=None,
        duration_seconds=3600,
        duration_explicit=True,
        now=datetime.now(UTC),
    )
    assert d is None and dur is None
