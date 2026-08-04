from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.config import DATA_DIR, DATABASE_URL
from quests.migrate import upgrade_to_head
from quests.models import Quest, QuestStatus, QuestStep
from quests.categories import ensure_categories

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _seed_data() -> list[Quest]:
    return [
        Quest(
            title="Найти следы у реки",
            description="Осмотреться у берега и найти улики.",
            status=QuestStatus.active,
            pinned=True,
            sort_order=1,
            steps=[
                QuestStep(title="Следы на илистом берегу", progress_current=1, progress_total=1, sort_order=1),
                QuestStep(title="Обрывок ткани", progress_current=1, progress_total=1, sort_order=2),
                QuestStep(title="Странный отпечаток", progress_current=0, progress_total=1, sort_order=3),
            ],
        ),
        Quest(
            title="Поговорить с кузнецом",
            description="Узнать про странный клинок.",
            status=QuestStatus.active,
            pinned=False,
            sort_order=2,
            steps=[
                QuestStep(title="Найти кузнеца на рынке", progress_current=0, progress_total=1, sort_order=1),
            ],
        ),
        Quest(
            title="Собрать травы для отвара",
            description="Нужно восемь пучков луговой травы.",
            status=QuestStatus.delayed,
            pinned=True,
            sort_order=3,
            steps=[
                QuestStep(
                    title="Луговая трава",
                    description="Собрать пучки",
                    progress_current=5,
                    progress_total=8,
                    sort_order=1,
                ),
            ],
        ),
        Quest(
            title="Разобрать почту",
            description="Инбокс не должен гнить.",
            status=QuestStatus.active,
            pinned=True,
            sort_order=4,
            steps=[
                QuestStep(title="Рабочая почта", progress_current=0, progress_total=1, sort_order=1),
                QuestStep(title="Личная почта", progress_current=1, progress_total=1, sort_order=2),
            ],
        ),
    ]


async def init_db(*, seed: bool = True) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    upgrade_to_head()

    async with SessionLocal() as session:
        await ensure_categories(session)
        await session.commit()

    if not seed:
        return

    async with SessionLocal() as session:
        result = await session.exec(select(Quest).limit(1))
        if result.first() is not None:
            return
        for quest in _seed_data():
            session.add(quest)
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


def quest_load_options():
    return (
        selectinload(Quest.steps),
        selectinload(Quest.category),
        selectinload(Quest.questline),
    )
