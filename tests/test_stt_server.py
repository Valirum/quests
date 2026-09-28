"""quests-stt HTTP wrapper — health + transcribe roundtrip (whisper itself mocked)."""

from __future__ import annotations

import asyncio

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from quests import stt_server
from quests.stt import SttError


class _FakeStt:
    def __init__(self, *, text: str | None = None, error: str | None = None) -> None:
        self._text = text
        self._error = error

    async def transcribe_file_async(self, path, *, settings=None):
        if self._error:
            raise SttError(self._error)
        return self._text


def _post_audio(monkeypatch, tmp_path, fake: _FakeStt) -> tuple[int, dict]:
    monkeypatch.setattr(stt_server, "get_stt", lambda: fake)

    async def go() -> tuple[int, dict]:
        app = stt_server.build_app()
        async with TestServer(app) as server, TestClient(server) as client:
            audio = tmp_path / "voice.ogg"
            audio.write_bytes(b"not-really-audio-bytes")
            with audio.open("rb") as fh:
                resp = await client.post("/transcribe", data={"audio": fh})
                body = await resp.json()
                return resp.status, body

    return asyncio.run(go())


def test_health() -> None:
    async def go() -> None:
        app = stt_server.build_app()
        async with TestServer(app) as server, TestClient(server) as client:
            resp = await client.get("/health")
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert "model" in data

    asyncio.run(go())


def test_transcribe_ok(monkeypatch, tmp_path) -> None:
    status, body = _post_audio(monkeypatch, tmp_path, _FakeStt(text="привет мир"))
    assert status == 200
    assert body["text"] == "привет мир"


def test_transcribe_stt_error_maps_to_422(monkeypatch, tmp_path) -> None:
    status, body = _post_audio(
        monkeypatch, tmp_path, _FakeStt(error="пустая расшифровка (тишина)")
    )
    assert status == 422
    assert "тишина" in body["error"]


def test_transcribe_missing_field_is_400() -> None:
    async def go() -> int:
        app = stt_server.build_app()
        async with TestServer(app) as server, TestClient(server) as client:
            form = aiohttp.FormData()
            form.add_field("not_audio", "x", content_type="text/plain")
            resp = await client.post("/transcribe", data=form)
            return resp.status

    assert asyncio.run(go()) == 400
