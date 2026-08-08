from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from quests.changelog import list_changes
from quests.events import hub
from quests.models import QuestChangeLogRead

router = APIRouter(tags=["events"])

# Server ping interval; dead tabs are dropped when ping send fails.
WS_RECV_TIMEOUT_SEC = 25.0


class FocusQuestBody(BaseModel):
    quest_id: int = Field(ge=1)


@router.get("/api/sync")
async def sync() -> dict[str, int]:
    """Lightweight revision for polling clients."""
    return {"revision": hub.revision}


@router.get("/api/events")
async def list_events(since: int = Query(default=0, ge=0)) -> dict:
    """Events with revision > since (for overlay toasts + HUD refresh)."""
    events = hub.events_since(since)
    return {"revision": hub.revision, "events": events}


@router.get("/api/quest-log", response_model=list[QuestChangeLogRead])
async def quest_change_log(
    limit: int = Query(default=100, ge=1, le=500),
    quest_id: int | None = Query(default=None, ge=1),
    before_id: int | None = Query(default=None, ge=1),
) -> list[QuestChangeLogRead]:
    """Durable quest activity (create/status/steps/edits). Skips step_progress."""
    return await list_changes(limit=limit, quest_id=quest_id, before_id=before_id)


@router.post("/api/ui/focus-quest")
async def focus_quest(body: FocusQuestBody) -> dict:
    """Ask open journal tabs to select a quest. Returns live delivery count."""
    clients = await hub.focus_quest(body.quest_id)
    return {
        "quest_id": body.quest_id,
        "clients": clients,
        "pending_focus": hub.peek_pending_focus(),
    }


@router.websocket("/ws")
async def websocket_events(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    ws.receive_text(), timeout=WS_RECV_TIMEOUT_SEC
                )
                # Client may reply to ping with "pong" / JSON — ignore body.
                _ = raw
            except asyncio.TimeoutError:
                # Probe: closed tabs often fail here even if earlier sends "worked".
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)
