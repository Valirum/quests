from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = "http://127.0.0.1:8765"


def resolve_api_base() -> str:
    """API base for HUD. Prefer QUESTS_API, then overlay.json api_base, else localhost."""
    env = (os.environ.get("QUESTS_API") or "").strip().rstrip("/")
    if env:
        return env
    try:
        from .config import CONFIG_PATH

        if CONFIG_PATH.is_file():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                file_base = str(data.get("api_base") or "").strip().rstrip("/")
                if file_base:
                    return file_base
    except Exception:
        pass
    return DEFAULT_API


API_BASE = resolve_api_base()

# Slightly longer when talking to a remote host.
_timeout_env = (os.environ.get("QUESTS_API_TIMEOUT") or "").strip()
try:
    DEFAULT_TIMEOUT = float(_timeout_env) if _timeout_env else (3.0 if "127.0.0.1" not in API_BASE and "localhost" not in API_BASE else 1.5)
except ValueError:
    DEFAULT_TIMEOUT = 1.5


def fetch_json(url: str, timeout: float | None = None):
    with urllib.request.urlopen(url, timeout=timeout if timeout is not None else DEFAULT_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def post_json(url: str, body: dict, timeout: float | None = None) -> dict | None:
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout if timeout is not None else DEFAULT_TIMEOUT) as resp:
        text = resp.read().decode()
        if not text:
            return None
        return json.loads(text)


def fetch_pinned() -> list[dict]:
    data = fetch_json(f"{API_BASE}/api/quests?pinned=true")
    return list(data)


def fetch_quests() -> list[dict]:
    data = fetch_json(f"{API_BASE}/api/quests")
    return list(data)


def fetch_categories() -> list[dict]:
    data = fetch_json(f"{API_BASE}/api/categories")
    return list(data)


def fetch_events(since: int) -> tuple[int, list[dict]]:
    q = urllib.parse.urlencode({"since": since})
    data = fetch_json(f"{API_BASE}/api/events?{q}", timeout=min(DEFAULT_TIMEOUT, 2.5))
    return int(data.get("revision", since)), list(data.get("events") or [])


def fetch_quest_log(*, limit: int = 16, quest_id: int | None = None) -> list[dict]:
    """Durable quest activity from /api/quest-log (newest first)."""
    params: dict[str, int] = {"limit": max(1, min(500, int(limit)))}
    if quest_id is not None:
        params["quest_id"] = int(quest_id)
    q = urllib.parse.urlencode(params)
    data = fetch_json(f"{API_BASE}/api/quest-log?{q}", timeout=min(DEFAULT_TIMEOUT, 2.5))
    return list(data) if isinstance(data, list) else []


def post_heartbeat(*, detail: str = "") -> None:
    """Best-effort liveness ping so the web UI can show HUD status."""
    try:
        post_json(
            f"{API_BASE}/api/health/heartbeat",
            {"component": "overlay", "detail": detail},
            timeout=min(DEFAULT_TIMEOUT, 2.0),
        )
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError, OSError):
        pass
