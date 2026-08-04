from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "http://127.0.0.1:8765"


def fetch_json(url: str, timeout: float = 1.5):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


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
    data = fetch_json(f"{API_BASE}/api/events?{q}", timeout=1.2)
    return int(data.get("revision", since)), list(data.get("events") or [])
