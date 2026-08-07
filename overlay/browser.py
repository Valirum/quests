"""Open / focus the web journal for a quest."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import webbrowser
from typing import Any

from .api_client import API_BASE


def _probe(url: str, timeout: float = 0.35) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def _is_loopback(url: str) -> bool:
    u = url.casefold()
    return "127.0.0.1" in u or "localhost" in u or "[::1]" in u


def resolve_web_base() -> str:
    """SPA base for opening a quest from the HUD.

    Order:
    1. ``QUESTS_WEB_URL`` if set
    2. Remote ``API_BASE`` (SPA is served by the same API host)
    3. Local Vite (:5173) / API SPA (:8765) when the HUD talks to localhost
    """
    env = (os.environ.get("QUESTS_WEB_URL") or "").strip().rstrip("/")
    if env:
        return env
    api = API_BASE.rstrip("/")
    # HUD pointed at a remote server → open that host, not a leftover local :8765.
    if api and not _is_loopback(api):
        return api
    for base in ("http://127.0.0.1:5173", "http://127.0.0.1:8765"):
        if _probe(base):
            return base
    return api or "http://127.0.0.1:8765"


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


def _niri_windows() -> list[dict[str, Any]]:
    niri = shutil.which("niri")
    if not niri:
        return []
    try:
        proc = subprocess.run(
            [niri, "msg", "-j", "windows"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [w for w in data if isinstance(w, dict)]
    return []


def _title_looks_like_journal(title: str) -> bool:
    t = title.casefold()
    if not t:
        return False
    # Prefer the real SPA title; avoid matching arbitrary "localhost" pages alone.
    if "quests" in t and "задачи" in t:
        return True
    if ":5173" in t or ":8765" in t:
        return True
    if "127.0.0.1" in t and ("quests" in t or "задачи" in t):
        return True
    return False


def _match_journal_window(windows: list[dict[str, Any]]) -> int | None:
    """Return niri window id for the journal's active tab, if found."""
    scored: list[tuple[int, int]] = []
    for win in windows:
        raw_id = win.get("id")
        try:
            wid = int(raw_id)
        except (TypeError, ValueError):
            continue
        title = str(win.get("title") or "")
        if not _title_looks_like_journal(title):
            continue
        # Prefer already-focused matches, then exact SPA title.
        t = title.casefold()
        score = 0
        if win.get("is_focused"):
            score += 10
        if "quests" in t and "задачи" in t:
            score += 5
        if ":5173" in t or ":8765" in t:
            score += 3
        scored.append((score, wid))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _raise_via_niri() -> int | None:
    """Focus journal window via niri. Returns window id or None."""
    wid = _match_journal_window(_niri_windows())
    if wid is None:
        return None
    niri = shutil.which("niri")
    if not niri:
        return None
    try:
        proc = subprocess.run(
            [niri, "msg", "action", "focus-window", "--id", str(wid)],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return wid


def focus_quest(quest_id: int) -> str:
    """Notify live journal tabs, then raise the browser window (niri) or open URL."""
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
        raised = _raise_via_niri()
        if raised is not None:
            return (
                f"focused existing tab (delivered={clients}) "
                f"+ raised niri id={raised} quest={qid}"
            )
        url = quest_url(qid)
        _open_url(url)
        return (
            f"focused existing tab (delivered={clients}) "
            f"+ opened {url}"
        )

    url = quest_url(qid)
    _open_url(url)
    return f"opened {url}"
