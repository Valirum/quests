"""Legacy no-op event hub for remaining Python domain helpers/tests.

Live WS / hooks are owned by the Go API (`go/internal/events`).
"""

from __future__ import annotations

from typing import Any


class Hub:
    revision: int = 0

    def publish(self, kind: str, **kwargs: Any) -> dict[str, Any]:
        self.revision += 1
        return {"type": "quests_changed", "kind": kind, "revision": self.revision, **kwargs}

    def broadcast(self, payload: dict[str, Any]) -> int:
        return 0


hub = Hub()
