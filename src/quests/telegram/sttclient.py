"""Async HTTP client for the quests-stt sidecar (voice → text)."""

from __future__ import annotations

from pathlib import Path

import aiohttp


class SttClientError(Exception):
    pass


class SttClient:
    def __init__(self, base: str, session: aiohttp.ClientSession) -> None:
        self.base = base.rstrip("/")
        self._session = session

    async def transcribe(self, path: Path) -> str:
        data = aiohttp.FormData()
        data.add_field(
            "audio",
            path.read_bytes(),
            filename=path.name,
            content_type="application/octet-stream",
        )
        try:
            async with self._session.post(
                f"{self.base}/transcribe",
                data=data,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                payload = await resp.json(content_type=None)
                if resp.status >= 400:
                    detail = (payload or {}).get("error") or f"HTTP {resp.status}"
                    raise SttClientError(str(detail))
        except aiohttp.ClientError as e:
            raise SttClientError(
                f"не удалось связаться со службой STT ({self.base}): {e}"
            ) from e
        return str((payload or {}).get("text") or "")
