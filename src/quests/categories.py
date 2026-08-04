"""Quest category helpers (seed + resolve)."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.models import CATEGORY_SEED, QuestCategory, utcnow


async def ensure_categories(session: AsyncSession) -> list[QuestCategory]:
    """Idempotent seed of the built-in category catalog."""
    existing = {
        row.slug: row for row in (await session.exec(select(QuestCategory))).all()
    }
    changed = False
    for slug, label, sort_order, color in CATEGORY_SEED:
        row = existing.get(slug)
        if row is None:
            session.add(
                QuestCategory(
                    slug=slug,
                    label=label,
                    sort_order=sort_order,
                    color=color,
                    created_at=utcnow(),
                )
            )
            changed = True
        elif (
            row.label != label
            or int(row.sort_order) != int(sort_order)
            or (getattr(row, "color", None) or "") != color
        ):
            row.label = label
            row.sort_order = int(sort_order)
            row.color = color
            session.add(row)
            changed = True
    if changed:
        await session.flush()
    rows = list(
        (
            await session.exec(
                select(QuestCategory).order_by(
                    QuestCategory.sort_order, QuestCategory.id
                )
            )
        ).all()
    )
    return rows


async def get_category_map(session: AsyncSession) -> dict[int, QuestCategory]:
    rows = await ensure_categories(session)
    return {int(r.id): r for r in rows if r.id is not None}


async def validate_category_id(
    session: AsyncSession, category_id: int | None
) -> int | None:
    if category_id is None:
        return None
    cats = await get_category_map(session)
    if int(category_id) not in cats:
        return None
    return int(category_id)
