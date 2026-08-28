"""Standalone LLM HTTP service: the action-batch web-form path in one long-lived process.

Wraps the same core (`extract_action_batch_sync`, `ActionExecutor`) the CLI
(`quests llm-action-preview`/`-apply`) uses, but as a persistent aiohttp
server instead of a `uv run` subprocess per request — avoids re-syncing/
re-compiling on every call, and lets the container that needs the Groq
proxy be a small, isolated service rather than a concern smeared onto the
main API container.

Routes:
  GET  /health           -> {"status": "ok"}
  POST /preview {text}   -> {"ok", "needs_clarification"?, "clarify_question"?, "batch"?, "preview"?}
  POST /apply {batch}    -> {"ok", "results"}
"""

from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web
from pydantic import ValidationError

from quests.actions_exec import ActionExecError, ActionExecutor
from quests.config import HOST, PORT
from quests.envload import load_dotenv_files
from quests.llm.actions import ActionBatch
from quests.llm.client import LlmError, extract_action_batch_sync

log = logging.getLogger("quests.llm.service")

API_BASE = (os.environ.get("QUESTS_API") or f"http://{HOST}:{PORT}").rstrip("/")


def _preview_payload(r) -> dict:
    return {"index": r.index, "action": r.action, "is_new": r.is_new, "before": r.before, "after": r.after}


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def handle_preview(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid JSON"}, status=400)

    text = str(body.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "text is required"}, status=400)

    try:
        batch = await asyncio.to_thread(extract_action_batch_sync, text)
    except LlmError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=502)

    if batch.needs_clarification:
        return web.json_response(
            {"ok": False, "needs_clarification": True, "clarify_question": batch.clarify_question}
        )

    executor = ActionExecutor(API_BASE)
    try:
        preview = await asyncio.to_thread(executor.run, batch, dry_run=True)
    except ActionExecError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=422)

    return web.json_response(
        {
            "ok": True,
            "needs_clarification": False,
            "batch": batch.model_dump(),
            "preview": [_preview_payload(r) for r in preview],
        }
    )


async def handle_apply(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid JSON"}, status=400)

    raw_batch = body.get("batch")
    if not raw_batch:
        return web.json_response({"ok": False, "error": "batch is required"}, status=400)

    try:
        batch = ActionBatch.model_validate(raw_batch)
    except ValidationError as e:
        return web.json_response({"ok": False, "error": f"батч не прошёл валидацию: {e}"}, status=400)

    executor = ActionExecutor(API_BASE)
    try:
        applied = await asyncio.to_thread(executor.run, batch, dry_run=False)
    except ActionExecError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=422)

    return web.json_response(
        {
            "ok": True,
            "results": [{"index": r.index, "action": r.action, "result": r.result} for r in applied],
        }
    )


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/preview", handle_preview)
    app.router.add_post("/apply", handle_apply)
    return app


def main() -> None:
    load_dotenv_files()
    logging.basicConfig(level=logging.INFO)
    host = os.environ.get("QUESTS_LLM_HOST") or "127.0.0.1"
    port = int(os.environ.get("QUESTS_LLM_SERVICE_PORT") or "8766")
    log.info("quests-llm listening on %s:%s (API_BASE=%s)", host, port, API_BASE)
    web.run_app(build_app(), host=host, port=port, print=None)


if __name__ == "__main__":
    main()
