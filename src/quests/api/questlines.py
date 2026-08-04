"""Questline CRUD API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.categories import validate_category_id
from quests.db import get_session
from quests.models import (
    Quest,
    QuestLine,
    QuestLineCreate,
    QuestLineRead,
    QuestLineUpdate,
    QuestTemplate,
    utcnow,
)
from quests.questlines import sync_member_categories

router = APIRouter(prefix="/api/questlines", tags=["questlines"])


def _line_load_options():
    return (selectinload(QuestLine.category),)


def line_to_read(line: QuestLine) -> QuestLineRead:
    cat = getattr(line, "category", None)
    return QuestLineRead(
        id=line.id,  # type: ignore[arg-type]
        title=line.title,
        description=line.description,
        category_id=line.category_id,
        color=line.color or "#9a9a9a",
        icon=line.icon or "document",
        created_at=line.created_at,
        updated_at=line.updated_at,
        category_slug=getattr(cat, "slug", None) if cat is not None else None,
        category_label=getattr(cat, "label", None) if cat is not None else None,
        category_color=getattr(cat, "color", None) if cat is not None else None,
    )


async def _get_line_or_404(session: AsyncSession, line_id: int) -> QuestLine:
    result = await session.exec(
        select(QuestLine).where(QuestLine.id == line_id).options(*_line_load_options())
    )
    line = result.first()
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Questline not found"
        )
    return line


@router.get("", response_model=list[QuestLineRead])
async def list_questlines(
    session: AsyncSession = Depends(get_session),
) -> list[QuestLineRead]:
    rows = (
        await session.exec(
            select(QuestLine)
            .options(*_line_load_options())
            .order_by(QuestLine.created_at, QuestLine.id)
        )
    ).all()
    return [line_to_read(r) for r in rows]


@router.get("/{line_id}", response_model=QuestLineRead)
async def get_questline(
    line_id: int,
    session: AsyncSession = Depends(get_session),
) -> QuestLineRead:
    return line_to_read(await _get_line_or_404(session, line_id))


@router.post("", response_model=QuestLineRead, status_code=status.HTTP_201_CREATED)
async def create_questline(
    payload: QuestLineCreate,
    session: AsyncSession = Depends(get_session),
) -> QuestLineRead:
    data = payload.model_dump()
    data["category_id"] = await validate_category_id(session, data.get("category_id"))
    if not data.get("color"):
        data["color"] = "#9a9a9a"
    if not data.get("icon"):
        data["icon"] = "document"
    line = QuestLine(**data)
    session.add(line)
    await session.commit()
    assert line.id is not None
    return line_to_read(await _get_line_or_404(session, int(line.id)))


@router.patch("/{line_id}", response_model=QuestLineRead)
async def update_questline(
    line_id: int,
    payload: QuestLineUpdate,
    session: AsyncSession = Depends(get_session),
) -> QuestLineRead:
    line = await _get_line_or_404(session, line_id)
    data = payload.model_dump(exclude_unset=True)
    category_touched = "category_id" in data
    if category_touched:
        data["category_id"] = await validate_category_id(
            session, data.get("category_id")
        )
    for key, value in data.items():
        setattr(line, key, value)
    line.updated_at = utcnow()
    if category_touched:
        await sync_member_categories(session, line)
    session.add(line)
    await session.commit()
    return line_to_read(await _get_line_or_404(session, line_id))


@router.delete("/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_questline(
    line_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    line = await _get_line_or_404(session, line_id)
    members = list(
        (await session.exec(select(Quest).where(Quest.questline_id == line_id))).all()
    )
    for q in members:
        q.questline_id = None
        session.add(q)
    tmpls = list(
        (
            await session.exec(
                select(QuestTemplate).where(QuestTemplate.questline_id == line_id)
            )
        ).all()
    )
    for t in tmpls:
        t.questline_id = None
        session.add(t)
    await session.delete(line)
    await session.commit()
