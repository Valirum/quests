from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from quests import health_registry

router = APIRouter(tags=["health"])

ComponentName = Literal["overlay", "telegram"]


class HeartbeatBody(BaseModel):
    component: ComponentName
    detail: str = Field(default="", max_length=200)


@router.get("/api/health")
async def health() -> dict[str, Any]:
    components = health_registry.snapshot()
    overall = "ok"
    for comp in components.values():
        if comp.get("status") != "ok":
            # API itself is up; degraded if a client is missing.
            overall = "degraded"
            break
    return {
        "status": overall,
        "api": {"status": "ok"},
        "components": components,
        "stale_after_seconds": health_registry.STALE_AFTER_S,
    }


@router.post("/api/health/heartbeat")
async def heartbeat(body: HeartbeatBody) -> dict[str, str]:
    try:
        health_registry.record(body.component, detail=body.detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "component": body.component}
