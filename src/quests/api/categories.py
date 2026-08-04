from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import ensure_categories
from quests.db import get_session
from quests.models import QuestCategoryRead

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[QuestCategoryRead])
async def list_categories(
    session: AsyncSession = Depends(get_session),
) -> list[QuestCategoryRead]:
    rows = await ensure_categories(session)
    await session.commit()
    return [
        QuestCategoryRead(
            id=int(r.id),  # type: ignore[arg-type]
            slug=r.slug,
            label=r.label,
            sort_order=int(r.sort_order),
            color=r.color or "#9a9a9a",
        )
        for r in rows
    ]
