"""Unit tests for step check-command helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from quests.checks import (
    MIN_INTERVAL_SEC,
    normalize_check_fields,
    parse_check_output,
    run_check_command,
    step_check_due,
)


def test_parse_check_output_plain_and_noisy():
    assert parse_check_output("7\n") == 7
    assert parse_check_output("files: 12") == 12
    assert parse_check_output("a\nb\n3") == 3
    assert parse_check_output("") is None
    assert parse_check_output("none") is None


def test_normalize_check_fields():
    step = SimpleNamespace(check_command="  ls  ", check_interval_seconds=10)
    normalize_check_fields(step)
    assert step.check_command == "ls"
    assert step.check_interval_seconds == MIN_INTERVAL_SEC

    step = SimpleNamespace(check_command="  ", check_interval_seconds=60)
    normalize_check_fields(step)
    assert step.check_command is None
    assert step.check_interval_seconds is None


def test_step_check_due():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    bare = SimpleNamespace(
        check_command=None, check_interval_seconds=None, check_last_run_at=None
    )
    assert step_check_due(bare, now=now) is False

    ready = SimpleNamespace(
        check_command="echo 1",
        check_interval_seconds=60,
        check_last_run_at=None,
    )
    assert step_check_due(ready, now=now) is True

    recent = SimpleNamespace(
        check_command="echo 1",
        check_interval_seconds=60,
        check_last_run_at=now - timedelta(seconds=30),
    )
    assert step_check_due(recent, now=now) is False

    old = SimpleNamespace(
        check_command="echo 1",
        check_interval_seconds=60,
        check_last_run_at=now - timedelta(seconds=90),
    )
    assert step_check_due(old, now=now) is True


def test_run_check_command_echo():
    assert run_check_command("echo 42") == 42
    assert run_check_command("printf 'count %s\\n' 9") == 9
