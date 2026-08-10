"""Changelog is written in the same request transaction (not fire-and-forget)."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlmodel import select

from quests.db import SessionLocal
from quests.main import app
from quests.models import QuestChangeLog


async def _kinds_for(quest_id: int) -> set[str]:
    async with SessionLocal() as session:
        rows = (
            await session.exec(
                select(QuestChangeLog).where(QuestChangeLog.quest_id == quest_id)
            )
        ).all()
    return {r.kind for r in rows}


def test_create_quest_writes_changelog_before_return() -> None:
    with TestClient(app) as client:
        res = client.post(
            "/api/quests?quiet=1&source=test",
            json={"title": "Log me", "steps": [{"title": "a"}]},
        )
        assert res.status_code == 201
        qid = res.json()["id"]

    kinds = asyncio.run(_kinds_for(qid))
    assert "quest_created" in kinds
