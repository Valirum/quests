from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

# How long a focus intent stays valid for late-connecting tabs.
FOCUS_TTL_SEC = 45.0


class EventHub:
    """In-process pub/sub + recent event log for polling clients (overlay)."""

    def __init__(self, *, history: int = 64) -> None:
        self.revision = 0
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._recent: deque[dict[str, Any]] = deque(maxlen=history)
        self._pending_focus: int | None = None
        self._pending_focus_at: float = 0.0

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            hello: dict[str, Any] = {"type": "hello", "revision": self.revision}
            focus = self._focus_if_fresh()
            if focus is not None:
                hello["pending_focus"] = focus
        await ws.send_text(json.dumps(hello))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    def _focus_if_fresh(self) -> int | None:
        if self._pending_focus is None:
            return None
        if time.monotonic() - self._pending_focus_at > FOCUS_TTL_SEC:
            return None
        return self._pending_focus

    def peek_pending_focus(self) -> int | None:
        return self._focus_if_fresh()

    async def set_pending_focus(self, quest_id: int) -> None:
        async with self._lock:
            self._pending_focus = int(quest_id)
            self._pending_focus_at = time.monotonic()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def events_since(self, since: int) -> list[dict[str, Any]]:
        return [e for e in self._recent if int(e.get("revision", 0)) > since]

    async def _prune_and_send(self, raw: str) -> int:
        """Send to all clients; drop dead ones. Returns successful deliveries."""
        dead: list[WebSocket] = []
        delivered = 0
        for ws in list(self._clients):
            try:
                if ws.client_state != WebSocketState.CONNECTED:
                    dead.append(ws)
                    continue
                await ws.send_text(raw)
                delivered += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
        return delivered

    async def broadcast(self, payload: dict[str, Any]) -> int:
        """Send a non-history message to live WS clients. Returns deliveries."""
        async with self._lock:
            return await self._prune_and_send(json.dumps(payload))

    async def focus_quest(self, quest_id: int) -> int:
        """Remember focus intent and notify live tabs. Returns deliveries."""
        await self.set_pending_focus(quest_id)
        return await self.broadcast(
            {"type": "ui_focus_quest", "quest_id": int(quest_id)}
        )

    async def publish(
        self,
        kind: str,
        *,
        quest_id: int | None = None,
        title: str = "",
        detail: str = "",
        sound: str | None = None,
        toast: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """Publish a domain event."""
        async with self._lock:
            self.revision += 1
            payload: dict[str, Any] = {
                "type": "quests_changed",
                "kind": kind,
                "revision": self.revision,
                "quest_id": quest_id,
                "title": title,
                "detail": detail,
                "sound": sound if sound is not None else kind,
                "toast": toast,
                **extra,
            }
            self._recent.append(payload)
            await self._prune_and_send(json.dumps(payload))
        # Outside the lock — hooks / durable log may I/O.
        try:
            from quests.hooks import dispatch_hooks

            asyncio.create_task(dispatch_hooks(payload))
        except Exception:
            pass
        try:
            from quests.changelog import persist_event

            asyncio.create_task(persist_event(payload))
        except Exception:
            pass
        return payload


hub = EventHub()
