"""CLI tests for hook subcommands (no API required)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from quests import hooks as hooks_mod
from quests.cli import main


@pytest.fixture()
def hooks_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "hooks.json"
    monkeypatch.setattr(hooks_mod, "HOOKS_PATH", path)
    return path


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def test_help_exits_zeroish():
    # argparse help exits via SystemExit(0)
    with pytest.raises(SystemExit) as ei:
        main(["-h"])
    assert ei.value.code == 0

    with pytest.raises(SystemExit) as ei:
        main(["hook", "-h"])
    assert ei.value.code == 0


def test_hook_cli_lifecycle(hooks_file: Path):
    code, out, err = _run(
        [
            "hook",
            "add",
            "-e",
            "complete",
            "-t",
            "script",
            "-c",
            "true",
            "--name",
            "cli-hook",
        ]
    )
    assert code == 0, err
    assert "добавлен" in out

    code, out, _ = _run(["hook", "list", "--json"])
    assert code == 0
    data = json.loads(out)
    assert len(data) == 1
    hook_id = data[0]["id"]
    assert data[0]["name"] == "cli-hook"
    assert data[0]["quest_id"] is None

    code, out, _ = _run(
        ["hook", "add", "-e", "step", "-t", "script", "-c", "true", "--quest", "42", "--json"]
    )
    assert code == 0
    quest_hook = json.loads(out)
    assert quest_hook["quest_id"] == 42

    code, out, _ = _run(["--json", "hook", "list", "--quest", "42"])
    assert code == 0
    only = json.loads(out)
    assert len(only) == 1 and only[0]["quest_id"] == 42

    code, out, _ = _run(["hook", "list", "--global", "--json"])
    assert code == 0
    glob = json.loads(out)
    assert len(glob) == 1 and glob[0]["id"] == hook_id

    code, _, _ = _run(["hook", "disable", hook_id])
    assert code == 0
    assert hooks_mod.get_hook(hook_id).enabled is False

    code, _, _ = _run(["hook", "enable", hook_id])
    assert code == 0
    assert hooks_mod.get_hook(hook_id).enabled is True

    code, out, _ = _run(["hook", "show", "cli-hook", "--json"])
    assert code == 0
    assert json.loads(out)["id"] == hook_id

    code, _, _ = _run(["hook", "remove", hook_id, "--json"])
    assert code == 0
    assert hooks_mod.get_hook(hook_id) is None


def test_hook_events_json(hooks_file: Path):
    code, out, _ = _run(["hook", "events", "--json"])
    assert code == 0
    data = json.loads(out)
    assert "complete" in data["aliases"]
    assert "quest_completed" in data["kinds"]


def test_hook_add_missing_command(hooks_file: Path):
    code, _, err = _run(["hook", "add", "-e", "complete", "-t", "script", "--json"])
    assert code != 0
    payload = json.loads(err)
    assert payload["ok"] is False
    assert "command" in payload["error"]
