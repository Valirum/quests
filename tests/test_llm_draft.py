"""Unit tests for LLM draft → API body (no live Ollama)."""

from __future__ import annotations

from datetime import UTC, datetime

from quests.llm.draft import draft_to_create_body, format_draft_preview
from quests.llm.schema import QuestDraft, quest_draft_json_schema


def test_draft_schema_has_required_keys() -> None:
    schema = quest_draft_json_schema()
    assert schema["type"] == "object"
    assert "title" in schema["properties"]
    assert "steps" in schema["required"]


def test_draft_to_body_relative_deadline() -> None:
    draft = QuestDraft(
        title="Почта",
        description="",
        category_slug="work",
        significance="common",
        pinned=False,
        deadline_in_minutes=60,
        duration_minutes=60,
        steps=["Рабочая", "Личная"],
        needs_clarification=False,
        clarify_question="",
    )
    cats = [{"id": 3, "slug": "work", "label": "Работа"}]
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    body = draft_to_create_body(draft, categories=cats, now=now)
    assert body["title"] == "Почта"
    assert body["category_id"] == 3
    assert body["duration_seconds"] == 3600
    assert body["deadline_at"].startswith("2026-08-05T13:00:00")
    assert len(body["steps"]) == 2
    assert body["steps"][0]["progress_total"] == 1


def test_draft_duration_only_implies_deadline() -> None:
    draft = QuestDraft.model_validate(
        {
            "title": "Разминка",
            "description": "",
            "category_slug": "health",
            "significance": "common",
            "pinned": False,
            "deadline_in_minutes": None,
            "duration_minutes": 30,
            "steps": [],
            "needs_clarification": False,
            "clarify_question": "",
        }
    )
    body = draft_to_create_body(draft, now=datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    assert body["duration_seconds"] == 1800
    assert "deadline_at" in body
    assert body["steps"][0]["title"] == "Разминка"


def test_unknown_category_dropped() -> None:
    draft = QuestDraft.model_validate(
        {
            "title": "X",
            "description": "",
            "category_slug": "nope",
            "significance": "epic",
            "pinned": False,
            "deadline_in_minutes": None,
            "duration_minutes": None,
            "steps": ["a"],
            "needs_clarification": False,
            "clarify_question": "",
        }
    )
    assert draft.category_slug is None
    body = draft_to_create_body(draft, categories=[{"id": 1, "slug": "work"}])
    assert "category_id" not in body
    assert body["significance"] == "epic"


def test_preview_contains_title() -> None:
    draft = QuestDraft(title="Тест", steps=["a"])
    text = format_draft_preview(draft)
    assert "Тест" in text
    assert "a" in text
