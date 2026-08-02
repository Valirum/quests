"""Open / focus the web journal for a quest."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import webbrowser

from .api_client import API_BASE


def _probe(url: str, timeout: float = 0.35) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def resolve_web_base() -> str:
    """Prefer Vite dev (:5173) when running; else API-served SPA (:8765)."""
    env = (os.environ.get("QUESTS_WEB_URL") or "").strip().rstrip("/")
    if env:
        return env
    for base in ("http://127.0.0.1:5173", "http://127.0.0.1:8765"):
        if _probe(base):
            return base
    return API_BASE.rstrip("/")


def quest_url(quest_id: int, base: str | None = None) -> str:
    root = (base or resolve_web_base()).rstrip("/")
    return f"{root}/?quest={int(quest_id)}"


def _open_url(url: str) -> None:
    # Prefer xdg-open on Linux — webbrowser.new=0 often focuses an old tab
    # without navigating to the new ?quest= id.
    xdg = shutil.which("xdg-open")
    if xdg:
        subprocess.Popen(
            [xdg, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return
    webbrowser.open(url, new=2, autoraise=True)


def focus_quest(quest_id: int) -> str:
    """Notify live journal tabs; open a browser tab only if nobody received it."""
    qid = int(quest_id)
    clients = 0
    try:
        req = urllib.request.Request(
            f"{API_BASE}/api/ui/focus-quest",
            data=json.dumps({"quest_id": qid}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            clients = int(data.get("clients") or 0)
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError):
        clients = 0

    if clients > 0:
        return f"focused existing tab (delivered={clients}) quest={qid}"

    url = quest_url(qid)
    _open_url(url)
    return f"opened {url}"
