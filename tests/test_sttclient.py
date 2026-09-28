"""Bot-side SttClient against a fake quests-stt sidecar."""

from __future__ import annotations

import asyncio

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer

from quests.telegram.sttclient import SttClient, SttClientError


def _fake_stt_app(*, text: str | None = None, error: str | None = None) -> web.Application:
    async def handle(_request: web.Request) -> web.Response:
        if error:
            return web.json_response({"error": error}, status=422)
        return web.json_response({"text": text})

    app = web.Application()
    app.router.add_post("/transcribe", handle)
    return app


def test_transcribe_ok(tmp_path) -> None:
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"fake-audio")

    async def go() -> str:
        app = _fake_stt_app(text="привет мир")
        async with TestServer(app) as server, aiohttp.ClientSession() as session:
            # Point the client at the fake server's own base URL.
            sc = SttClient(str(server.make_url("")), session)
            return await sc.transcribe(audio)

    assert asyncio.run(go()) == "привет мир"


def test_transcribe_error_raises(tmp_path) -> None:
    audio = tmp_path / "voice.ogg"
    audio.write_bytes(b"fake-audio")

    async def go() -> None:
        app = _fake_stt_app(error="пустая расшифровка")
        async with TestServer(app) as server, aiohttp.ClientSession() as session:
            sc = SttClient(str(server.make_url("")), session)
            await sc.transcribe(audio)

    try:
        asyncio.run(go())
    except SttClientError as e:
        assert "пустая расшифровка" in str(e)
    else:
        raise AssertionError("expected SttClientError")
