"""Resolve quest / step / questline id into a full related context bundle."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.api.questlines import line_to_read
from quests.db import get_session, quest_load_options
from quests.models import Quest, QuestLine, QuestLineRead, QuestRead, QuestStep
from quests.serializers import quest_to_read

router = APIRouter(prefix="/api", tags=["context"])


class ContextFocus(SQLModel):
    type: Literal["quest", "step", "questline"]
    id: int


class ContextRead(SQLModel):
    focus: ContextFocus
    questline: Optional[QuestLineRead] = None
    quests: list[QuestRead] = Field(default_factory=list)


def _line_load_options():
    return (selectinload(QuestLine.category),)


async def _get_line(session: AsyncSession, line_id: int) -> QuestLine:
    result = await session.exec(
        select(QuestLine).where(QuestLine.id == line_id).options(*_line_load_options())
    )
    line = result.first()
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Questline not found"
        )
    return line


async def _load_quests_for_line(
    session: AsyncSession, line_id: int
) -> list[Quest]:
    rows = (
        await session.exec(
            select(Quest)
            .where(Quest.questline_id == line_id)
            .options(*quest_load_options())
            .order_by(Quest.created_at.desc(), Quest.id.desc())
        )
    ).all()
    return list(rows)


async def _load_quest(session: AsyncSession, quest_id: int) -> Quest:
    result = await session.exec(
        select(Quest).where(Quest.id == quest_id).options(*quest_load_options())
    )
    quest = result.first()
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )
    return quest


async def _bundle(
    session: AsyncSession,
    *,
    focus_type: Literal["quest", "step", "questline"],
    focus_id: int,
    quest: Quest | None,
    line_id: int | None,
) -> ContextRead:
    line_read: QuestLineRead | None = None
    quests: list[Quest] = []

    if line_id is not None:
        line = await _get_line(session, line_id)
        line_read = line_to_read(line)
        quests = await _load_quests_for_line(session, line_id)
    elif quest is not None:
        quests = [quest]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nothing to resolve"
        )

    return ContextRead(
        focus=ContextFocus(type=focus_type, id=focus_id),
        questline=line_read,
        quests=[quest_to_read(q) for q in quests],
    )


@router.get("/context", response_model=ContextRead)
async def get_context(
    quest: int | None = Query(default=None, description="quest id"),
    step: int | None = Query(default=None, description="step id"),
    questline: int | None = Query(default=None, description="questline id"),
    session: AsyncSession = Depends(get_session),
) -> ContextRead:
    """Return questline (if any) + sibling quests + all steps/progress.

    Pass exactly one of ``quest``, ``step``, or ``questline``.
    """
    provided = [
        ("quest", quest),
        ("step", step),
        ("questline", questline),
    ]
    chosen = [(k, v) for k, v in provided if v is not None]
    if len(chosen) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of: quest, step, questline",
        )

    kind, eid = chosen[0]
    assert eid is not None

    if kind == "step":
        row = (
            await session.exec(select(QuestStep).where(QuestStep.id == eid))
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Step not found"
            )
        q = await _load_quest(session, int(row.quest_id))
        return await _bundle(
            session,
            focus_type="step",
            focus_id=eid,
            quest=q,
            line_id=q.questline_id,
        )

    if kind == "quest":
        q = await _load_quest(session, eid)
        return await _bundle(
            session,
            focus_type="quest",
            focus_id=eid,
            quest=q,
            line_id=q.questline_id,
        )

    # questline
    return await _bundle(
        session,
        focus_type="questline",
        focus_id=eid,
        quest=None,
        line_id=eid,
    )
