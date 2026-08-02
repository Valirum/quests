"""CLI quest command parsing/formatting with mocked API."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

import pytest

from quests.cli import main


def _run(argv: list[str]) -> tuple[int, str, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture()
def api_mock(monkeypatch: pytest.MonkeyPatch):
    store: dict[str, Any] = {"quests": {}, "seq": 0}

    def api_request(method: str, path: str, *, body=None, query=None):
        method = method.upper()
        if method == "GET" and path == "/api/quests":
            items = list(store["quests"].values())
            if query:
                if query.get("status"):
                    items = [q for q in items if q["status"] == query["status"]]
                if query.get("pinned") == "true":
                    items = [q for q in items if q["pinned"]]
                if query.get("pinned") == "false":
                    items = [q for q in items if not q["pinned"]]
            return items

        if method == "POST" and path == "/api/quests":
            store["seq"] += 1
            qid = store["seq"]
            steps_in = body.get("steps") or [
                {"title": body["title"], "progress_current": 0, "progress_total": 1}
            ]
            steps = []
            for i, s in enumerate(steps_in):
                steps.append(
                    {
                        "id": i + 1,
                        "quest_id": qid,
                        "title": s["title"],
                        "progress_current": int(s.get("progress_current") or 0),
                        "progress_total": int(s.get("progress_total") or 1),
                        "done": False,
                        "sort_order": i,
                    }
                )
                steps[-1]["done"] = steps[-1]["progress_current"] >= steps[-1]["progress_total"]
            q = {
                "id": qid,
                "title": body["title"],
                "description": body.get("description") or "",
                "status": body.get("status") or "active",
                "significance": body.get("significance") or "common",
                "pinned": bool(body.get("pinned")),
                "progress_label": f"0 / {len(steps)}",
                "steps": steps,
            }
            store["quests"][qid] = q
            return q

        if method == "GET" and path.startswith("/api/quests/"):
            qid = int(path.rsplit("/", 1)[-1])
            return store["quests"][qid]

        if method == "PATCH" and "/steps/" in path:
            # /api/quests/{id}/steps/{step_id}
            parts = path.strip("/").split("/")
            qid = int(parts[2])
            step_id = int(parts[4])
            q = store["quests"][qid]
            for s in q["steps"]:
                if s["id"] == step_id:
                    if body and "progress_current" in body:
                        s["progress_current"] = int(body["progress_current"])
                        s["done"] = s["progress_current"] >= s["progress_total"]
            done = sum(1 for s in q["steps"] if s["done"])
            q["progress_label"] = f"{done} / {len(q['steps'])}"
            if done == len(q["steps"]):
                q["status"] = "completed"
            return q

        if method == "PATCH" and path.startswith("/api/quests/"):
            qid = int(path.rsplit("/", 1)[-1])
            q = store["quests"][qid]
            q.update(body or {})
            return q

        if method == "DELETE" and path.startswith("/api/quests/"):
            qid = int(path.rsplit("/", 1)[-1])
            store["quests"].pop(qid, None)
            return None

        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr("quests.cli.api_request", api_request)
    return store


def test_cli_quest_flow(api_mock):
    code, out, err = _run(
        [
            "add",
            "CLI quest",
            "--pin",
            "--step",
            "A",
            "--step",
            "B",
            "--json",
        ]
    )
    assert code == 0, err
    q = json.loads(out)
    assert q["title"] == "CLI quest"
    assert q["pinned"] is True
    assert len(q["steps"]) == 2
    qid = q["id"]

    code, out, err = _run(["list", "--pinned", "--json"])
    assert code == 0, err
    assert any(i["id"] == qid for i in json.loads(out))

    code, out, err = _run(["list"])
    assert code == 0, err
    assert "CLI quest" in out
    assert "★" in out

    code, out, err = _run(["step", str(qid), "--title", "A", "--done", "--json"])
    assert code == 0, err
    updated = json.loads(out)
    step_a = next(s for s in updated["steps"] if s["title"] == "A")
    assert step_a["done"] is True

    code, out, err = _run(["show", str(qid)])
    assert code == 0, err
    assert "CLI quest" in out
    assert "A" in out

    code, out, err = _run(["complete", str(qid), "--json"])
    assert code == 0, err
    assert json.loads(out)["status"] == "completed"

    code, out, err = _run(["unpin", str(qid), "--json"])
    assert code == 0, err
    assert json.loads(out)["pinned"] is False

    code, out, err = _run(["delete", str(qid), "--json"])
    assert code == 0, err
    assert json.loads(out)["deleted"] == qid


def test_cli_api_error_json(api_mock, monkeypatch: pytest.MonkeyPatch):
    from quests.cli import CliError

    def boom(*_a, **_k):
        raise CliError("API 404: Quest not found")

    monkeypatch.setattr("quests.cli.api_request", boom)
    code, _, err = _run(["show", "999", "--json"])
    assert code == 1
    assert json.loads(err)["ok"] is False
