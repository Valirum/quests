"""GET /api/context — resolve quest/step/questline into a related bundle."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quests.main import app


def test_context_requires_exactly_one_id() -> None:
    with TestClient(app) as client:
        assert client.get("/api/context").status_code == 400
        assert client.get("/api/context?quest=1&step=1").status_code == 400


def test_context_by_quest_alone() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/quests?quiet=1",
            json={
                "title": "Solo context",
                "steps": [
                    {"title": "one", "progress_current": 0, "progress_total": 2},
                    {"title": "two", "progress_current": 1, "progress_total": 1},
                ],
            },
        )
        assert created.status_code == 201
        qid = created.json()["id"]

        res = client.get(f"/api/context?quest={qid}")
        assert res.status_code == 200
        body = res.json()
        assert body["focus"] == {"type": "quest", "id": qid}
        assert body["questline"] is None
        assert len(body["quests"]) == 1
        assert body["quests"][0]["id"] == qid
        assert len(body["quests"][0]["steps"]) == 2


def test_context_by_step_and_questline() -> None:
    with TestClient(app) as client:
        line = client.post(
            "/api/questlines",
            json={"title": "Line ctx", "color": "#abc", "icon": "flag"},
        )
        assert line.status_code == 201
        lid = line.json()["id"]

        a = client.post(
            "/api/quests?quiet=1",
            json={
                "title": "A",
                "questline_id": lid,
                "steps": [{"title": "sa", "progress_current": 0, "progress_total": 1}],
            },
        )
        b = client.post(
            "/api/quests?quiet=1",
            json={
                "title": "B",
                "questline_id": lid,
                "steps": [{"title": "sb", "progress_current": 1, "progress_total": 1}],
            },
        )
        assert a.status_code == 201 and b.status_code == 201
        step_id = a.json()["steps"][0]["id"]

        by_step = client.get(f"/api/context?step={step_id}").json()
        assert by_step["focus"] == {"type": "step", "id": step_id}
        assert by_step["questline"]["id"] == lid
        assert {q["id"] for q in by_step["quests"]} == {a.json()["id"], b.json()["id"]}

        by_line = client.get(f"/api/context?questline={lid}").json()
        assert by_line["focus"] == {"type": "questline", "id": lid}
        assert by_line["questline"]["id"] == lid
        assert len(by_line["quests"]) == 2
