"""deadline_set_with_open_window — parity with Go WindowNotifier (quest=269)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quests.timeutil import deadline_set_with_open_window


def test_postpone_style_suppresses() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert deadline_set_with_open_window(
        now + timedelta(minutes=30), 1800, now
    )


def test_natural_crossing_fires() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert not deadline_set_with_open_window(
        now + timedelta(minutes=30), 1800, now - timedelta(days=1)
    )


def test_within_skew_suppresses() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert deadline_set_with_open_window(
        now + timedelta(minutes=30), 1800, now - timedelta(seconds=2)
    )


def test_beyond_skew_fires() -> None:
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert not deadline_set_with_open_window(
        now + timedelta(minutes=30), 1800, now - timedelta(seconds=10)
    )
