"""API: add / update / delete individual quest steps."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quests.main import app


def test_step_add_edit_delete() -> None:
    with TestClient(app) as client:
        res = client.post(
            "/api/quests?quiet=1",
            json={
                "title": "Step CRUD",
                "steps": [
                    {"title": "A", "progress_current": 0, "progress_total": 1},
                    {"title": "B", "progress_current": 0, "progress_total": 1},
                ],
            },
        )
        assert res.status_code == 201, res.text
        q = res.json()
        qid = q["id"]
        assert len(q["steps"]) == 2

        res = client.post(
            f"/api/quests/{qid}/steps?quiet=1",
            json={"title": "C", "progress_total": 3},
        )
        assert res.status_code == 201, res.text
        q = res.json()
        assert len(q["steps"]) == 3
        c = next(s for s in q["steps"] if s["title"] == "C")
        assert c["progress_total"] == 3
        assert c["sort_order"] == max(s["sort_order"] for s in q["steps"])

        res = client.patch(
            f"/api/quests/{qid}/steps/{c['id']}?quiet=1",
            json={"title": "C-renamed", "progress_current": 1},
        )
        assert res.status_code == 200, res.text
        q = res.json()
        c2 = next(s for s in q["steps"] if s["id"] == c["id"])
        assert c2["title"] == "C-renamed"
        assert c2["progress_current"] == 1

        res = client.delete(f"/api/quests/{qid}/steps/{c['id']}?quiet=1")
        assert res.status_code == 200, res.text
        q = res.json()
        assert len(q["steps"]) == 2
        assert all(s["id"] != c["id"] for s in q["steps"])

        # cannot delete last remaining step after removing one more
        other = q["steps"][1]["id"]
        only = q["steps"][0]["id"]
        assert client.delete(f"/api/quests/{qid}/steps/{other}?quiet=1").status_code == 200
        res = client.delete(f"/api/quests/{qid}/steps/{only}?quiet=1")
        assert res.status_code == 400

        client.delete(f"/api/quests/{qid}?quiet=1")
