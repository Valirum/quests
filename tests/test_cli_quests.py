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
    store: dict[str, Any] = {
        "quests": {},
        "questlines": {},
        "seq": 0,
        "ql_seq": 0,
        "categories": [
            {
                "id": 1,
                "slug": "work",
                "label": "Работа",
                "sort_order": 10,
                "color": "#5a8a9a",
            },
            {
                "id": 3,
                "slug": "health",
                "label": "Здоровье",
                "sort_order": 30,
                "color": "#7a9e3a",
            },
        ],
    }

    def api_request(method: str, path: str, *, body=None, query=None):
        method = method.upper()
        if method == "GET" and path == "/api/categories":
            return list(store["categories"])

        if method == "GET" and path == "/api/questlines":
            return list(store["questlines"].values())

        if method == "POST" and path == "/api/questlines":
            store["ql_seq"] += 1
            lid = store["ql_seq"]
            cat_id = body.get("category_id")
            cat = next((c for c in store["categories"] if c["id"] == cat_id), None)
            row = {
                "id": lid,
                "title": body["title"],
                "description": body.get("description") or "",
                "category_id": cat_id,
                "color": body.get("color") or "#9a9a9a",
                "icon": body.get("icon") or "document",
                "category_slug": cat["slug"] if cat else None,
                "category_label": cat["label"] if cat else None,
            }
            store["questlines"][lid] = row
            return row

        if method == "GET" and path.startswith("/api/questlines/"):
            lid = int(path.rsplit("/", 1)[-1])
            return store["questlines"][lid]

        if method == "PATCH" and path.startswith("/api/questlines/"):
            lid = int(path.rsplit("/", 1)[-1])
            row = store["questlines"][lid]
            row.update(body or {})
            cat = next(
                (c for c in store["categories"] if c["id"] == row.get("category_id")),
                None,
            )
            row["category_slug"] = cat["slug"] if cat else None
            row["category_label"] = cat["label"] if cat else None
            # sync member categories
            for q in store["quests"].values():
                if q.get("questline_id") == lid:
                    q["category_id"] = row.get("category_id")
                    q["category_slug"] = row.get("category_slug")
                    q["category_label"] = row.get("category_label")
            return row

        if method == "DELETE" and path.startswith("/api/questlines/"):
            lid = int(path.rsplit("/", 1)[-1])
            store["questlines"].pop(lid, None)
            for q in store["quests"].values():
                if q.get("questline_id") == lid:
                    q["questline_id"] = None
                    q["questline_title"] = None
            return None

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
            ql_id = body.get("questline_id")
            cat_id = body.get("category_id")
            ql = store["questlines"].get(ql_id) if ql_id else None
            if ql is not None:
                cat_id = ql.get("category_id")
            cat = next((c for c in store["categories"] if c["id"] == cat_id), None)
            q = {
                "id": qid,
                "title": body["title"],
                "description": body.get("description") or "",
                "status": body.get("status") or "active",
                "significance": body.get("significance") or "common",
                "pinned": bool(body.get("pinned")),
                "progress_label": f"0 / {len(steps)}",
                "steps": steps,
                "category_id": cat_id,
                "category_slug": cat["slug"] if cat else None,
                "category_label": cat["label"] if cat else None,
                "questline_id": ql_id,
                "questline_title": ql["title"] if ql else None,
                "questline_color": ql["color"] if ql else None,
                "questline_icon": ql["icon"] if ql else None,
            }
            store["quests"][qid] = q
            return q

        if method == "GET" and path.startswith("/api/quests/") and "/steps" not in path:
            qid = int(path.rsplit("/", 1)[-1])
            return store["quests"][qid]

        if method == "POST" and path.endswith("/steps") and path.startswith("/api/quests/"):
            # /api/quests/{id}/steps
            qid = int(path.strip("/").split("/")[2])
            q = store["quests"][qid]
            store["seq"] += 1  # reuse seq for step ids uniqueness across quests
            step_id = max((s["id"] for s in q["steps"]), default=0) + 1
            sort = body.get("sort_order")
            if sort is None:
                sort = max((s.get("sort_order") or 0 for s in q["steps"]), default=-1) + 1
            step = {
                "id": step_id,
                "quest_id": qid,
                "title": body["title"],
                "description": body.get("description") or "",
                "progress_current": int(body.get("progress_current") or 0),
                "progress_total": int(body.get("progress_total") or 1),
                "sort_order": int(sort),
                "done": False,
            }
            step["done"] = step["progress_current"] >= step["progress_total"]
            q["steps"].append(step)
            done = sum(1 for s in q["steps"] if s["done"])
            q["progress_label"] = f"{done} / {len(q['steps'])}"
            if done == len(q["steps"]) and q["steps"]:
                q["status"] = "completed"
            elif q["status"] == "completed" and done < len(q["steps"]):
                q["status"] = "active"
            return q

        if method == "PATCH" and "/steps/" in path:
            # /api/quests/{id}/steps/{step_id}
            parts = path.strip("/").split("/")
            qid = int(parts[2])
            step_id = int(parts[4])
            q = store["quests"][qid]
            for s in q["steps"]:
                if s["id"] == step_id:
                    if body:
                        if "progress_current" in body:
                            s["progress_current"] = int(body["progress_current"])
                        if "progress_total" in body:
                            s["progress_total"] = int(body["progress_total"])
                        if "title" in body:
                            s["title"] = body["title"]
                        if "description" in body:
                            s["description"] = body["description"]
                        if "sort_order" in body:
                            s["sort_order"] = int(body["sort_order"])
                        s["done"] = s["progress_current"] >= s["progress_total"]
            done = sum(1 for s in q["steps"] if s["done"])
            q["progress_label"] = f"{done} / {len(q['steps'])}"
            if done == len(q["steps"]) and q["steps"]:
                q["status"] = "completed"
            elif q["status"] == "completed" and done < len(q["steps"]):
                q["status"] = "active"
            return q

        if method == "DELETE" and "/steps/" in path:
            parts = path.strip("/").split("/")
            qid = int(parts[2])
            step_id = int(parts[4])
            q = store["quests"][qid]
            if len(q["steps"]) <= 1:
                raise AssertionError("Cannot delete the last step")
            q["steps"] = [s for s in q["steps"] if s["id"] != step_id]
            done = sum(1 for s in q["steps"] if s["done"])
            q["progress_label"] = f"{done} / {len(q['steps'])}"
            if done == len(q["steps"]) and q["steps"]:
                q["status"] = "completed"
            elif q["status"] == "completed" and done < len(q["steps"]):
                q["status"] = "active"
            return q

        if method == "PATCH" and path.startswith("/api/quests/"):
            qid = int(path.rsplit("/", 1)[-1])
            q = store["quests"][qid]
            payload = dict(body or {})
            if "questline_id" in payload:
                ql_id = payload["questline_id"]
                ql = store["questlines"].get(ql_id) if ql_id else None
                q["questline_id"] = ql_id
                q["questline_title"] = ql["title"] if ql else None
                q["questline_color"] = ql["color"] if ql else None
                q["questline_icon"] = ql["icon"] if ql else None
                if ql is not None:
                    payload["category_id"] = ql.get("category_id")
                payload.pop("questline_id", None)
            if "category_id" in payload:
                cat_id = payload["category_id"]
                cat = next((c for c in store["categories"] if c["id"] == cat_id), None)
                q["category_id"] = cat_id
                q["category_slug"] = cat["slug"] if cat else None
                q["category_label"] = cat["label"] if cat else None
                payload.pop("category_id", None)
            q.update(payload)
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


def test_cli_categories_and_questlines(api_mock):
    code, out, err = _run(["categories", "--json"])
    assert code == 0, err
    cats = json.loads(out)
    assert any(c["slug"] == "work" for c in cats)

    code, out, err = _run(
        [
            "questline",
            "add",
            "Проект",
            "--category",
            "work",
            "--icon",
            "flag",
            "--color",
            "#5a8a9a",
            "--json",
        ]
    )
    assert code == 0, err
    line = json.loads(out)
    assert line["title"] == "Проект"
    assert line["category_slug"] == "work"
    lid = line["id"]

    code, out, err = _run(["add", "MVP", "--questline", str(lid), "--json"])
    assert code == 0, err
    q = json.loads(out)
    assert q["questline_id"] == lid
    assert q["category_slug"] == "work"
    qid = q["id"]

    code, out, err = _run(["list", "--questline", "Проект"])
    assert code == 0, err
    assert "MVP" in out
    assert "work" in out

    code, out, err = _run(
        ["questline", "set", str(lid), "--category", "health", "--json"]
    )
    assert code == 0, err
    assert json.loads(out)["category_slug"] == "health"

    code, out, err = _run(["show", str(qid), "--json"])
    assert code == 0, err
    assert json.loads(out)["category_slug"] == "health"

    code, out, err = _run(["set", str(qid), "--questline", "none", "--json"])
    assert code == 0, err
    assert json.loads(out)["questline_id"] is None

    code, out, err = _run(["questline", "delete", str(lid), "--json"])
    assert code == 0, err
    assert json.loads(out)["deleted"] == lid


def test_cli_api_error_json(api_mock, monkeypatch: pytest.MonkeyPatch):
    from quests.cli import CliError

    def boom(*_a, **_k):
        raise CliError("API 404: Quest not found")

    monkeypatch.setattr("quests.cli.api_request", boom)
    code, _, err = _run(["show", "999", "--json"])
    assert code == 1
    assert json.loads(err)["ok"] is False


def test_cli_step_add_edit_rm(api_mock):
    code, out, err = _run(["add", "Steps", "--step", "A", "--step", "B", "--json"])
    assert code == 0, err
    q = json.loads(out)
    qid = q["id"]
    assert len(q["steps"]) == 2

    code, out, err = _run(["step-add", str(qid), "C", "--total", "2", "--json"])
    assert code == 0, err
    q = json.loads(out)
    assert len(q["steps"]) == 3
    c = next(s for s in q["steps"] if s["title"] == "C")
    assert c["progress_total"] == 2

    code, out, err = _run(
        ["step-edit", str(qid), str(c["id"]), "--title", "C2", "--set", "1", "--json"]
    )
    assert code == 0, err
    q = json.loads(out)
    c2 = next(s for s in q["steps"] if s["id"] == c["id"])
    assert c2["title"] == "C2"
    assert c2["progress_current"] == 1

    code, out, err = _run(["step-rm", str(qid), str(c["id"]), "--json"])
    assert code == 0, err
    q = json.loads(out)
    assert len(q["steps"]) == 2
    assert all(s["title"] != "C2" for s in q["steps"])
