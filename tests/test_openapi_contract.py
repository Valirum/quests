"""Freeze key OpenAPI shapes so a Go port can lock the contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quests.main import app


def test_openapi_quest_update_has_no_steps_replace() -> None:
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    assert "QuestUpdate" in schemas
    props = schemas["QuestUpdate"].get("properties") or {}
    assert "steps" not in props, "PATCH /quests must not replace steps[]; use step CRUD"

    create_props = schemas["QuestCreate"].get("properties") or {}
    assert "steps" in create_props

    read_props = schemas["QuestRead"].get("properties") or {}
    for key in (
        "id",
        "title",
        "status",
        "steps",
        "deadline_at",
        "duration_seconds",
        "remaining_seconds",
        "timer_tone",
        "urgent",
    ):
        assert key in read_props, f"QuestRead missing {key}"


def test_openapi_core_paths_present() -> None:
    spec = app.openapi()
    paths = spec["paths"]
    for path in (
        "/api/quests",
        "/api/quests/{quest_id}",
        "/api/quests/{quest_id}/steps",
        "/api/quests/{quest_id}/steps/{step_id}",
        "/api/stats",
        "/api/events",
        "/api/hero",
    ):
        assert path in paths, f"missing path {path}"


def test_openapi_export_roundtrip_via_docs() -> None:
    with TestClient(app) as client:
        res = client.get("/openapi.json")
        assert res.status_code == 200
        body = res.json()
        assert body["info"]["title"] == "Quests"
        assert "QuestRead" in body["components"]["schemas"]
