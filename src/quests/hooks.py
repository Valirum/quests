"""User-defined hooks: script / webhook / unix socket.

Hooks live in ``data/hooks.json`` (override with ``QUESTS_HOOKS``).

Scope:
  - global — ``quest_id`` is null → any matching event
  - quest  — ``quest_id`` set → only that quest

Events accept aliases (``complete``, ``step``, ``status``) or raw kinds
(``quest_completed``, ``step_completed``, …).
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from quests.config import DATA_DIR

log = logging.getLogger("quests.hooks")

HOOKS_PATH = Path(os.environ.get("QUESTS_HOOKS") or DATA_DIR / "hooks.json")

HookType = Literal["script", "webhook", "socket"]

# CLI-friendly aliases → concrete event kinds published by the server.
EVENT_ALIASES: dict[str, tuple[str, ...]] = {
    "complete": ("quest_completed",),
    "on_complete": ("quest_completed",),
    "step": ("step_completed", "step_progress"),
    "on_step": ("step_completed", "step_progress"),
    "status": (
        "status_changed",
        "quest_completed",
        "quest_failed",
        "quest_delayed",
    ),
    "on_status_change": (
        "status_changed",
        "quest_completed",
        "quest_failed",
        "quest_delayed",
    ),
    "fail": ("quest_failed",),
    "created": ("quest_created",),
    "deleted": ("quest_deleted",),
    "appear": ("quest_appeared", "quest_created"),
    "start": ("quest_started",),
    "window": ("quest_started",),
    "delay": ("quest_delayed",),
}

KNOWN_KINDS = frozenset(
    {
        "quest_created",
        "quest_appeared",
        "quest_started",
        "quest_completed",
        "quest_failed",
        "quest_delayed",
        "quest_deleted",
        "quest_updated",
        "status_changed",
        "step_completed",
        "step_progress",
        "pin_changed",
        "startup",
    }
)


def expand_events(names: Iterable[str]) -> list[str]:
    """Expand aliases; keep unknown tokens as raw kinds (forward-compat)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        key = str(raw or "").strip().lower()
        if not key:
            continue
        expanded = EVENT_ALIASES.get(key)
        targets = expanded if expanded is not None else (key,)
        for kind in targets:
            if kind not in seen:
                seen.add(kind)
                out.append(kind)
    return out


@dataclass
class Hook:
    id: str
    events: list[str]
    type: HookType
    enabled: bool = True
    quest_id: int | None = None
    name: str = ""
    command: str = ""
    url: str = ""
    path: str = ""
    timeout_sec: float = 30.0
    # Original aliases as entered (for display); events holds expanded kinds.
    events_raw: list[str] = field(default_factory=list)

    def matches(self, kind: str, quest_id: int | None) -> bool:
        if not self.enabled:
            return False
        if kind not in self.events:
            return False
        if self.quest_id is None:
            return True
        return quest_id is not None and int(self.quest_id) == int(quest_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "events": list(self.events_raw or self.events),
            "events_expanded": list(self.events),
            "type": self.type,
            "quest_id": self.quest_id,
            "command": self.command,
            "url": self.url,
            "path": self.path,
            "timeout_sec": self.timeout_sec,
        }


def _hook_from_dict(raw: dict[str, Any]) -> Hook | None:
    try:
        hook_type = str(raw.get("type") or "script").strip().lower()
        if hook_type not in {"script", "webhook", "socket"}:
            return None
        events_raw = [str(x) for x in (raw.get("events") or [])]
        expanded = expand_events(events_raw)
        if not expanded:
            return None
        quest_raw = raw.get("quest_id")
        quest_id = None if quest_raw in (None, "", False) else int(quest_raw)
        return Hook(
            id=str(raw.get("id") or uuid.uuid4().hex[:12]),
            events=expanded,
            events_raw=events_raw or list(expanded),
            type=hook_type,  # type: ignore[arg-type]
            enabled=bool(raw.get("enabled", True)),
            quest_id=quest_id,
            name=str(raw.get("name") or ""),
            command=str(raw.get("command") or ""),
            url=str(raw.get("url") or ""),
            path=str(raw.get("path") or ""),
            timeout_sec=float(raw.get("timeout_sec") or 30),
        )
    except (TypeError, ValueError):
        return None


def load_hooks(path: Path | None = None) -> list[Hook]:
    p = path or HOOKS_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("hooks") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out: list[Hook] = []
    for item in items:
        if isinstance(item, dict):
            hook = _hook_from_dict(item)
            if hook is not None:
                out.append(hook)
    return out


def save_hooks(hooks: list[Hook], path: Path | None = None) -> None:
    p = path or HOOKS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "hooks": [
            {
                "id": h.id,
                "name": h.name,
                "enabled": h.enabled,
                "events": list(h.events_raw or h.events),
                "type": h.type,
                "quest_id": h.quest_id,
                "command": h.command,
                "url": h.url,
                "path": h.path,
                "timeout_sec": h.timeout_sec,
            }
            for h in hooks
        ]
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_hook(hook_id: str, path: Path | None = None) -> Hook | None:
    want = str(hook_id).strip()
    for h in load_hooks(path):
        if h.id == want or (h.name and h.name == want):
            return h
    return None


def add_hook(
    *,
    events: list[str],
    hook_type: HookType,
    quest_id: int | None = None,
    name: str = "",
    command: str = "",
    url: str = "",
    path: str = "",
    timeout_sec: float = 30.0,
    enabled: bool = True,
    store_path: Path | None = None,
) -> Hook:
    expanded = expand_events(events)
    if not expanded:
        raise ValueError("нужен хотя бы один event")
    if hook_type == "script" and not command.strip():
        raise ValueError("script-хук требует --command")
    if hook_type == "webhook" and not url.strip():
        raise ValueError("webhook-хук требует --url")
    if hook_type == "socket" and not path.strip():
        raise ValueError("socket-хук требует --path")

    hooks = load_hooks(store_path)
    hook = Hook(
        id=uuid.uuid4().hex[:12],
        events=expanded,
        events_raw=[str(e).strip() for e in events if str(e).strip()],
        type=hook_type,
        enabled=enabled,
        quest_id=quest_id,
        name=name.strip(),
        command=command,
        url=url,
        path=path,
        timeout_sec=timeout_sec,
    )
    hooks.append(hook)
    save_hooks(hooks, store_path)
    return hook


def remove_hook(hook_id: str, store_path: Path | None = None) -> Hook | None:
    hooks = load_hooks(store_path)
    keep: list[Hook] = []
    removed: Hook | None = None
    for h in hooks:
        if removed is None and (h.id == hook_id or (h.name and h.name == hook_id)):
            removed = h
            continue
        keep.append(h)
    if removed is not None:
        save_hooks(keep, store_path)
    return removed


def set_hook_enabled(
    hook_id: str, enabled: bool, store_path: Path | None = None
) -> Hook | None:
    hooks = load_hooks(store_path)
    found: Hook | None = None
    for h in hooks:
        if h.id == hook_id or (h.name and h.name == hook_id):
            h.enabled = enabled
            found = h
            break
    if found is not None:
        save_hooks(hooks, store_path)
    return found


def matching_hooks(kind: str, quest_id: int | None, path: Path | None = None) -> list[Hook]:
    return [h for h in load_hooks(path) if h.matches(kind, quest_id)]


def run_hook(hook: Hook, event: dict[str, Any]) -> None:
    """Execute one hook synchronously (call from a worker thread)."""
    payload = json.dumps(event, ensure_ascii=False, default=str)
    timeout = max(1.0, float(hook.timeout_sec or 30))
    try:
        if hook.type == "script":
            env = os.environ.copy()
            env["QUESTS_KIND"] = str(event.get("kind") or "")
            env["QUESTS_QUEST_ID"] = "" if event.get("quest_id") is None else str(event["quest_id"])
            env["QUESTS_TITLE"] = str(event.get("title") or "")
            env["QUESTS_DETAIL"] = str(event.get("detail") or "")
            env["QUESTS_PAYLOAD"] = payload
            subprocess.run(
                hook.command,
                shell=True,
                input=payload + "\n",
                text=True,
                env=env,
                timeout=timeout,
                check=False,
            )
        elif hook.type == "webhook":
            req = urllib.request.Request(
                hook.url,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()
        elif hook.type == "socket":
            data = (payload + "\n").encode("utf-8")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(hook.path)
                sock.sendall(data)
    except Exception as exc:
        log.warning("hook %s (%s) failed: %s", hook.id, hook.type, exc)


def dispatch_hooks_sync(event: dict[str, Any], path: Path | None = None) -> int:
    """Run matching hooks in-process. Returns number of hooks invoked."""
    kind = str(event.get("kind") or "")
    if not kind or kind == "startup":
        return 0
    qid = event.get("quest_id")
    quest_id = None if qid is None else int(qid)
    matched = matching_hooks(kind, quest_id, path)
    for hook in matched:
        run_hook(hook, event)
    return len(matched)


async def dispatch_hooks(event: dict[str, Any], path: Path | None = None) -> int:
    """Async wrapper: run hooks off the event loop."""
    import asyncio

    return await asyncio.to_thread(dispatch_hooks_sync, event, path)
