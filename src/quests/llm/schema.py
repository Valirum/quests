"""JSON Schema + Pydantic draft for constrained LLM output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from quests.models import CATEGORY_SEED, QuestSignificance

CATEGORY_SLUGS: tuple[str, ...] = tuple(slug for slug, *_ in CATEGORY_SEED)
SIGNIFICANCE_VALUES: tuple[str, ...] = tuple(s.value for s in QuestSignificance)


class QuestDraft(BaseModel):
    """One structured quest proposal (relative times, not ISO)."""

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
    # Legacy single-draft clarify flags (bundle prefers top-level).
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


class QuestDraftBundle(BaseModel):
    """Ranked variations (best first) + optional clarification."""

    needs_clarification: bool = False
    clarify_question: str = ""
    variations: list[QuestDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_variations(self) -> QuestDraftBundle:
        if self.needs_clarification:
            if not self.variations:
                # Stub so callers always have something to show.
                self.variations = [
                    QuestDraft(
                        title="Уточнение",
                        needs_clarification=True,
                        clarify_question=self.clarify_question,
                    )
                ]
            return self
        if not self.variations:
            raise ValueError("variations empty")
        # Cap at 3; keep order (most likely first).
        self.variations = self.variations[:3]
        return self

    @property
    def primary(self) -> QuestDraft:
        return self.variations[0]


def _variation_schema() -> dict[str, Any]:
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
        ],
    }


def quest_draft_json_schema() -> dict[str, Any]:
    """JSON Schema for constrained decode (bundle with ranked variations)."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "needs_clarification": {"type": "boolean"},
            "clarify_question": {"type": "string"},
            "variations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": _variation_schema(),
            },
        },
        "required": ["needs_clarification", "clarify_question", "variations"],
    }


def system_prompt(*, now_local: str, tz_name: str) -> str:
    cats = ", ".join(CATEGORY_SLUGS)
    sigs = ", ".join(SIGNIFICANCE_VALUES)
    schema = quest_draft_json_schema()
    return (
        "Ты извлекаешь задачу для журнала Quests из свободного текста пользователя.\n"
        "КРИТИЧНО:\n"
        "- Ответь ОДНИМ JSON-объектом и больше ничем (без markdown, без ```, без пояснений, "
        "без рассуждений до/после JSON).\n"
        "- Даже если нужны уточнения — всё равно верни валидный JSON.\n"
        "- Не вызывай инструменты, не читай и не меняй файлы, не исследуй репозиторий.\n"
        "- Не выдумывай факты, которых нет во вводе (кроме оценки duration — см. ниже).\n"
        "- Не выдумывай лишние шаги: только явно названные или очевидный короткий список "
        "из текста; иначе один шаг ≈ title.\n"
        "Формат ответа:\n"
        "  • needs_clarification / clarify_question — на уровне корня;\n"
        "  • variations — массив из РОВНО 3 вариантов черновика (если задача понятна), "
        "упорядоченных по убыванию уверенности: [0] самый вероятный, затем запасные "
        "с другими формулировками title/steps/сроков/категории, где уместно;\n"
        "  • если needs_clarification=true — variations из 1 черновика-заглушки "
        "(title всё равно заполни) + короткий clarify_question по-русски.\n"
        f"Сейчас локально: {now_local} ({tz_name}). От него считай все минуты.\n"
        f"category_slug — один из: {cats}, либо null если неясно.\n"
        f"significance — один из: {sigs} (по умолчанию common; "
        "epic/legendary только если пользователь явно сказал «эпик/легендарн…» "
        "или сравнимая важность).\n"
        "pinned=true ТОЛЬКО если пользователь явно просит закрепить "
        "(«закрепи», «в избранное», «pin»); иначе false.\n"
        "title — 2–3 слова (не целое предложение); детали — в description и steps.\n"
        "Время только в минутах от «сейчас»:\n"
        "  deadline_in_minutes — когда должно быть готово (null если срока нет);\n"
        "  duration_minutes — длина активного окна, которое КОНЧАЕТСЯ на дедлайне "
        "(окно = [дедлайн − duration, дедлайн]). Это НЕ «сколько осталось до срока».\n"
        "Календарные якоря (переведи в минуты от сейчас):\n"
        "  • «до вечера» / «вечером» → сегодня ~20:00–21:00 местного времени;\n"
        "  • «завтра утром» → завтра ~09:00–10:00;\n"
        "  • «к пятнице» / «до понедельника» → ближайшая такая дата в будущем "
        "(если сегодня уже этот день и время прошло — следующая неделя);\n"
        "  • «через N дней/часов» → ровно N·1440 / N·60 минут.\n"
        "Правила deadline vs duration:\n"
        "  1) Явно «без срока / не срочно / когда удобно / без дедлайна» → "
        "deadline_in_minutes=null; duration_minutes=названная длина или null.\n"
        "  2) Только длительность («на час», «займёт 30 минут») и НЕТ отказа от срока → "
        "deadline_in_minutes ≈ duration_minutes (оба из этой длины).\n"
        "  3) Есть и срок, и длительность («до вечера, полтора часа», "
        "«к пятнице час работы») → deadline=срок, duration=длительность; "
        "они РАЗНЫЕ, если срок длиннее работы.\n"
        "  4) Только далёкий срок («через 3 дня», «до пятницы») без длительности → "
        "deadline=срок; duration оцени 15–120 мин для бытовых/офисных "
        "(или до ~4ч для крупной работы); "
        "НИКОГДА не копируй далёкий deadline в duration.\n"
        "  5) Если оба заданы: duration_minutes ≤ deadline_in_minutes.\n"
        "needs_clarification=true только если нет понятной задачи "
        "(например «сделай то самое»); category/срок/pin — не повод.\n"
        "Вариации: отличай title/steps/category/timing там, где текст допускает "
        "несколько разумных прочтений; не делай три одинаковых копии.\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
