"""JSON Schema + Pydantic draft for constrained LLM output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from quests.models import CATEGORY_SEED, QuestSignificance

CATEGORY_SLUGS: tuple[str, ...] = tuple(slug for slug, *_ in CATEGORY_SEED)
SIGNIFICANCE_VALUES: tuple[str, ...] = tuple(s.value for s in QuestSignificance)


class QuestDraft(BaseModel):
    """Structured quest proposal from the model (relative times, not ISO)."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category_slug: str | None = None
    significance: str = QuestSignificance.common.value
    pinned: bool = False
    # Minutes from *now* until deadline. Null = no deadline.
    deadline_in_minutes: int | None = Field(default=None, ge=1)
    # Length of the active window ending at deadline (minutes).
    duration_minutes: int | None = Field(default=None, ge=1)
    steps: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarify_question: str = ""

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        t = (v or "").strip()
        if not t:
            raise ValueError("empty title")
        return t[:200]

    @field_validator("category_slug")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        if v is None or str(v).strip() in {"", "null", "none", "None"}:
            return None
        slug = str(v).strip().lower()
        if slug not in CATEGORY_SLUGS:
            return None
        return slug

    @field_validator("significance")
    @classmethod
    def _sig(cls, v: str) -> str:
        s = (v or QuestSignificance.common.value).strip().lower()
        if s not in SIGNIFICANCE_VALUES:
            return QuestSignificance.common.value
        return s

    @field_validator("steps")
    @classmethod
    def _steps(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v or []:
            t = str(item).strip()
            if t:
                out.append(t[:200])
        return out[:20]


def quest_draft_json_schema() -> dict[str, Any]:
    """JSON Schema for Ollama `format=` / constrained decode."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": "string"},
            "category_slug": {
                "anyOf": [
                    {"type": "string", "enum": list(CATEGORY_SLUGS)},
                    {"type": "null"},
                ]
            },
            "significance": {
                "type": "string",
                "enum": list(SIGNIFICANCE_VALUES),
            },
            "pinned": {"type": "boolean"},
            "deadline_in_minutes": {
                "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]
            },
            "duration_minutes": {
                "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]
            },
            "steps": {
                "type": "array",
                "items": {"type": "string", "minLength": 1, "maxLength": 200},
                "maxItems": 20,
            },
            "needs_clarification": {"type": "boolean"},
            "clarify_question": {"type": "string"},
        },
        "required": [
            "title",
            "description",
            "category_slug",
            "significance",
            "pinned",
            "deadline_in_minutes",
            "duration_minutes",
            "steps",
            "needs_clarification",
            "clarify_question",
        ],
    }


def system_prompt(*, now_local: str, tz_name: str) -> str:
    cats = ", ".join(CATEGORY_SLUGS)
    sigs = ", ".join(SIGNIFICANCE_VALUES)
    schema = quest_draft_json_schema()
    return (
        "Ты извлекаешь задачу для журнала Quests из свободного текста пользователя.\n"
        "КРИТИЧНО:\n"
        "- Ответь ОДНИМ JSON-объектом и больше ничем (без markdown, без ```, без пояснений).\n"
        "- Не вызывай инструменты, не читай и не меняй файлы, не исследуй репозиторий.\n"
        "- Не выдумывай факты, которых нет во вводе (кроме разумной оценки длительности окна — см. ниже).\n"
        f"Сейчас локально: {now_local} ({tz_name}).\n"
        f"category_slug — один из: {cats}, либо null если неясно.\n"
        f"significance — один из: {sigs} (по умолчанию common).\n"
        "title — короткая формулировка задачи в 2–3 слова (не целое предложение); "
        "детали и контекст — в description и steps.\n"
        "steps — короткие названия шагов; если шаги не названы — один шаг = title "
        "или разбей очевидный список.\n"
        "Время только относительно «сейчас» (минуты):\n"
        "  deadline_in_minutes — когда задача должна быть готова (null если срока нет);\n"
        "  duration_minutes — длина активного окна работы, которое кончается на дедлайне "
        "(окно = [дедлайн − duration, дедлайн]).\n"
        "Правила окна (duration) — ВАЖНО, не копируй дедлайн бездумно:\n"
        "  • «на час / займёт 30 минут» без отдельного дедлайна → "
        "deadline_in_minutes ≈ duration_minutes (оба из сказанной длины);\n"
        "  • названы и срок, и длительность («до пятницы, час работы») → "
        "deadline = срок, duration = названная длительность;\n"
        "  • есть только дедлайн («сдать через 2 дня», «до вечера») → "
        "deadline = срок, а duration оцени сам как реалистичное время на выполнение "
        "(обычно 15–120 минут для бытовых/рабочих задач; "
        "НЕ ставь duration_minutes = deadline_in_minutes, если до срока больше пары часов);\n"
        "  • duration_minutes всегда ≤ deadline_in_minutes, если оба заданы.\n"
        "Если критично не хватает данных (нет понятного title) — "
        "needs_clarification=true и короткий clarify_question по-русски; "
        "title всё равно заполни черновиком.\n"
        "Не ставь needs_clarification из-за мелочей: category/срок можно оставить null.\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
