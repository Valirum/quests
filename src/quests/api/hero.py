from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import get_session
from quests.hero import decay_momentum, hero_to_read
from quests.models import HeroSheetRead

router = APIRouter(prefix="/api/hero", tags=["hero"])


@router.get("", response_model=HeroSheetRead)
async def get_hero(session: AsyncSession = Depends(get_session)) -> HeroSheetRead:
    await decay_momentum(session)
    await session.commit()
    return await hero_to_read(session)
