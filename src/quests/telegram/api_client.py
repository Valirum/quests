"""Async HTTP client for local Quests API (no Telegram proxy)."""

from __future__ import annotations

import json
from typing import Any

import aiohttp


class ApiError(Exception):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class QuestsApi:
    def __init__(self, base: str, session: aiohttp.ClientSession) -> None:
        self.base = base.rstrip("/")
        self._session = session

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base}{path}"
        params = {k: v for k, v in (query or {}).items() if v is not None} or None
        try:
            async with self._session.request(
                method.upper(),
                url,
                json=body,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                if resp.status >= 400:
                    detail = raw.decode("utf-8", errors="replace")
                    try:
                        parsed = json.loads(detail)
                        detail = str(parsed.get("detail", detail))
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass
                    raise ApiError(f"API {resp.status}: {detail}", status=resp.status)
                if not raw:
                    return None
                return await resp.json(content_type=None)
        except aiohttp.ClientError as e:
            raise ApiError(
                f"не удалось связаться с API ({self.base}): {e}. "
                "Запусти сервер: ./scripts/run-server.sh"
            ) from e

    async def list_quests(self, *, status: str | None = "active") -> list[dict]:
        data = await self.request("GET", "/api/quests", query={"status": status})
        return list(data or [])

    async def get_quest(self, quest_id: int) -> dict:
        return await self.request("GET", f"/api/quests/{quest_id}")

    async def create_quest(self, body: dict[str, Any]) -> dict:
        return await self.request("POST", "/api/quests", body=body)

    async def patch_quest(self, quest_id: int, body: dict[str, Any]) -> dict:
        return await self.request("PATCH", f"/api/quests/{quest_id}", body=body)

    async def patch_step(
        self, quest_id: int, step_id: int, body: dict[str, Any]
    ) -> dict:
        return await self.request(
            "PATCH", f"/api/quests/{quest_id}/steps/{step_id}", body=body
        )

    async def list_categories(self) -> list[dict]:
        data = await self.request("GET", "/api/categories")
        return list(data or [])

    async def events_since(self, since: int) -> dict:
        return await self.request("GET", "/api/events", query={"since": since})

    async def sync_revision(self) -> int:
        data = await self.request("GET", "/api/sync")
        return int((data or {}).get("revision") or 0)
