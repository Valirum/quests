"""quests-stt — minimal internal HTTP wrapper around WhisperStt.

Split out of the bot process (quest: shrink quests-bot image) so the
ctranslate2/onnxruntime/av stack only rebuilds when STT itself changes, not
on every aiogram bump. Not for public exposure: no auth, no rate limiting —
docker-compose binds it to the host's loopback only, same trust boundary as
talking to the Quests API from the bot.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from aiohttp import web

from quests.stt import SttError, get_stt, load_stt_settings

log = logging.getLogger("quests.sttserver")

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8766
# A voice note is a few hundred KB at most; this just guards against a
# misbehaving/malicious client on the same host wedging the process.
MAX_UPLOAD_BYTES = 32 * 1024 * 1024


async def handle_health(_request: web.Request) -> web.Response:
    settings = load_stt_settings()
    return web.json_response({"ok": True, "model": settings.model})


async def handle_transcribe(request: web.Request) -> web.Response:
    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "audio":
        raise web.HTTPBadRequest(text="ожидалось multipart-поле 'audio'")

    suffix = Path(field.filename or "audio.ogg").suffix or ".ogg"
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            tmp = Path(fh.name)
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                fh.write(chunk)
        text = await get_stt().transcribe_file_async(tmp, settings=load_stt_settings())
    except SttError as e:
        return web.json_response({"error": str(e)}, status=422)
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    return web.json_response({"text": text})


def build_app() -> web.Application:
    app = web.Application(client_max_size=MAX_UPLOAD_BYTES)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/transcribe", handle_transcribe)
    return app


def main() -> None:
    from quests.envload import load_dotenv_files

    loaded = load_dotenv_files()
    logging.basicConfig(
        level=os.environ.get("QUESTS_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if loaded is not None:
        log.info("loaded env from %s", loaded)

    host = os.environ.get("QUESTS_STT_HOST", DEFAULT_HOST)
    port = int(os.environ.get("QUESTS_STT_PORT", str(DEFAULT_PORT)))
    settings = load_stt_settings()
    log.info(
        "quests-stt starting on %s:%s model=%s device=%s compute=%s",
        host,
        port,
        settings.model,
        settings.device,
        settings.compute_type,
    )
    web.run_app(build_app(), host=host, port=port, print=None)


if __name__ == "__main__":
    main()
