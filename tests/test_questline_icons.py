"""Custom questline icon upload / serve / clear."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quests.main import app


def test_questline_custom_icon_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("quests.questline_icons.ICON_DIR", tmp_path / "icons")
    with TestClient(app) as client:
        created = client.post(
            "/api/questlines",
            json={"title": "With icon", "color": "#abc", "icon": "flag"},
        )
        assert created.status_code == 201
        lid = created.json()["id"]
        assert created.json().get("icon_url") is None

        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
            b"\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        up = client.post(
            f"/api/questlines/{lid}/icon",
            files={"file": ("x.png", png, "image/png")},
        )
        assert up.status_code == 200, up.text
        body = up.json()
        assert body["custom_icon"] == f"{lid}.png"
        assert body["icon_url"] and body["icon_url"].startswith(
            f"/api/questlines/{lid}/icon"
        )
        assert body["icon"] == "flag"

        got = client.get(f"/api/questlines/{lid}/icon")
        assert got.status_code == 200
        assert got.content.startswith(b"\x89PNG")

        cleared = client.delete(f"/api/questlines/{lid}/icon")
        assert cleared.status_code == 200
        assert cleared.json()["custom_icon"] is None
        assert cleared.json()["icon_url"] is None
        assert client.get(f"/api/questlines/{lid}/icon").status_code == 404

        client.delete(f"/api/questlines/{lid}")
