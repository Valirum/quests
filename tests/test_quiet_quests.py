"""Quiet quest mutations: toast=False on ?quiet=1."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quests.events import hub
from quests.main import app


def test_create_quest_quiet_sets_toast_false() -> None:
    before = hub.revision
    with TestClient(app) as client:
        res = client.post(
            "/api/quests?quiet=1",
            json={"title": "Quiet create", "steps": [{"title": "a"}]},
        )
    assert res.status_code == 201
    created = [e for e in hub.events_since(before) if e.get("kind") == "quest_created"]
    assert created
    assert created[-1].get("toast") is False


def test_create_quest_loud_by_default() -> None:
    before = hub.revision
    with TestClient(app) as client:
        res = client.post(
            "/api/quests",
            json={"title": "Loud create", "steps": [{"title": "a"}]},
        )
    assert res.status_code == 201
    created = [e for e in hub.events_since(before) if e.get("kind") == "quest_created"]
    assert created
    assert created[-1].get("toast") is True
