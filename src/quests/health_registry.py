"""In-memory heartbeats from overlay / telegram clients."""

from __future__ import annotations

import threading
import time
from typing import Any

# Consider offline if no heartbeat within this window.
STALE_AFTER_S = 20.0

_lock = threading.Lock()
# component -> { "ts": float, "detail": str }
_beats: dict[str, dict[str, Any]] = {}

KNOWN = ("overlay", "telegram")


def record(component: str, *, detail: str = "") -> None:
    key = str(component or "").strip().lower()
    if key not in KNOWN:
        raise ValueError(f"unknown component: {component}")
    with _lock:
        _beats[key] = {"ts": time.monotonic(), "detail": (detail or "")[:200], "wall": time.time()}


def snapshot(now: float | None = None) -> dict[str, Any]:
    mono = time.monotonic() if now is None else now
    out: dict[str, Any] = {}
    with _lock:
        for key in KNOWN:
            beat = _beats.get(key)
            if not beat:
                out[key] = {
                    "status": "offline",
                    "age_seconds": None,
                    "last_seen_at": None,
                    "detail": "",
                }
                continue
            age = max(0.0, mono - float(beat["ts"]))
            wall = beat.get("wall")
            status = "ok" if age <= STALE_AFTER_S else "offline"
            out[key] = {
                "status": status,
                "age_seconds": round(age, 1),
                "last_seen_at": (
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall))
                    if isinstance(wall, (int, float))
                    else None
                ),
                "detail": beat.get("detail") or "",
            }
    return out
