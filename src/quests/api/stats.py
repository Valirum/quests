"""GET /api/stats — daily activity + periodic template streaks."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import get_session
from quests.stats import build_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


class DailyBucket(BaseModel):
    date: str
    issued: int
    completed: int
    failed: int


class TemplateSummary(BaseModel):
    id: int
    title: str
    enabled: bool


class TemplateBar(BaseModel):
    period_key: str
    status: str
    outcome: str
    quest_id: Optional[int] = None


class TemplateStats(BaseModel):
    id: int
    title: str
    current_streak: int
    longest_streak: int
    closed: int
    total: int
    close_rate: float
    bars: list[TemplateBar] = Field(default_factory=list)


class StatsRead(BaseModel):
    range: dict[str, str]
    daily: list[DailyBucket]
    templates: list[TemplateSummary]
    template: Optional[TemplateStats] = None


@router.get("", response_model=StatsRead)
async def get_stats(
    days: int | None = Query(default=30, ge=1, le=366),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    template_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    data = await build_stats(
        session,
        days=days,
        date_from=date_from,
        date_to=date_to,
        template_id=template_id,
    )
    if template_id is not None and data.get("template") is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return data
