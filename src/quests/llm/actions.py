"""JSON Schema + Pydantic for LLM-driven multi-step quest actions.

Same philosophy as ``llm/schema.py`` (constrained decode into a fixed
Pydantic shape, no agentic tool-calling loop): the model emits an ordered
list of flat ``Action`` objects. Each action maps 1:1 onto one of the
existing quests-MCP tool functions (create_questline / create_quest /
add_step / update_step / delete_step / update_quest); the executor
(``quests.actions_exec``) resolves ``*_ref`` cross-references and calls
those same HTTP endpoints.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from quests.models import QuestStatus

ACTION_KINDS: tuple[str, ...] = (
    "create_questline",
    "create_quest",
    "add_step",
    "update_step",
    "delete_step",
    "update_quest",
)

STATUS_VALUES: tuple[str, ...] = tuple(s.value for s in QuestStatus)


class ActionStep(BaseModel):
    """Inline step for create_quest's ``steps`` list."""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    progress_total: int = Field(default=1, ge=1)
    progress_current: int = Field(default=0, ge=0)


class Action(BaseModel):
    index: int = Field(ge=0)
    action: Literal[
        "create_questline",
        "create_quest",
        "add_step",
        "update_step",
        "delete_step",
        "update_quest",
    ]

    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    status: str | None = None
    significance: str | None = None
    pinned: bool | None = None
    sort_order: int | None = None
    deadline_at: str | None = None
    duration_seconds: int | None = None

    category: str | None = None
    category_id: int | None = None
    questline: str | None = None
    questline_id: int | None = None
    clear_questline: bool = False
    color: str | None = None
    icon: str | None = None

    quest_id: int | None = None
    step_id: int | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    steps: list[ActionStep] | None = None

    questline_id_ref: int | None = None
    quest_id_ref: int | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        if s not in STATUS_VALUES:
            raise ValueError(f"bad status {v!r}; expected one of {STATUS_VALUES}")
        return s

    @model_validator(mode="after")
    def _require_fields(self) -> Action:
        if self.action == "create_questline" and not self.title:
            raise ValueError("create_questline requires title")
        if self.action == "create_quest" and not self.title:
            raise ValueError("create_quest requires title")
        if self.action in {"add_step", "update_step", "delete_step", "update_quest"}:
            if self.quest_id is None and self.quest_id_ref is None:
                raise ValueError(f"{self.action} requires quest_id or quest_id_ref")
        if self.action == "add_step" and not self.title:
            raise ValueError("add_step requires title")
        if self.action in {"update_step", "delete_step"} and self.step_id is None:
            raise ValueError(f"{self.action} requires step_id")
        if self.quest_id_ref is not None and self.quest_id_ref >= self.index:
            raise ValueError("quest_id_ref must point to an earlier action")
        if self.questline_id_ref is not None and self.questline_id_ref >= self.index:
            raise ValueError("questline_id_ref must point to an earlier action")
        return self


class ActionBatch(BaseModel):
    needs_clarification: bool = False
    clarify_question: str = ""
    actions: list[Action] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> ActionBatch:
        if self.needs_clarification:
            return self
        if not self.actions:
            raise ValueError("actions empty")
        for i, a in enumerate(self.actions):
            if a.index != i:
                raise ValueError(f"action[{i}].index={a.index}, expected {i}")
        return self


def _action_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "index": {"type": "integer", "minimum": 0},
            "action": {"type": "string", "enum": list(ACTION_KINDS)},
            "title": {"anyOf": [{"type": "string", "maxLength": 200}, {"type": "null"}]},
            "description": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "status": {"anyOf": [{"type": "string", "enum": list(STATUS_VALUES)}, {"type": "null"}]},
            "significance": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "pinned": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
            "sort_order": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "deadline_at": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "duration_seconds": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "category": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "category_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "questline": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "questline_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "clear_questline": {"type": "boolean"},
            "color": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "icon": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "quest_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "step_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "progress_current": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "progress_total": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "steps": {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "title": {"type": "string", "minLength": 1, "maxLength": 200},
                                "description": {"type": "string"},
                                "progress_total": {"type": "integer", "minimum": 1},
                                "progress_current": {"type": "integer", "minimum": 0},
                            },
                            "required": ["title", "description", "progress_total", "progress_current"],
                        },
                        "maxItems": 20,
                    },
                    {"type": "null"},
                ]
            },
            "questline_id_ref": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "quest_id_ref": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        },
        "required": [
            "index", "action", "title", "description", "status", "significance",
            "pinned", "sort_order", "deadline_at", "duration_seconds",
            "category", "category_id", "questline", "questline_id",
            "clear_questline", "color", "icon", "quest_id", "step_id",
            "progress_current", "progress_total", "steps",
            "questline_id_ref", "quest_id_ref",
        ],
    }


def action_batch_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "needs_clarification": {"type": "boolean"},
            "clarify_question": {"type": "string"},
            "actions": {
                "type": "array",
                "items": _action_schema(),
                "maxItems": 20,
            },
        },
        "required": ["needs_clarification", "clarify_question", "actions"],
    }


def actions_system_prompt() -> str:
    schema = action_batch_json_schema()
    statuses = ", ".join(STATUS_VALUES)
    return (
        "Ты преобразуешь запрос пользователя в список действий (actions) над "
        "журналом квестов Quests.\n"
        "СИНТАКСИС ССЫЛОК: quest=N / questline=N / step=N — это точные числовые id, "
        "подставленные фронтом через автокомплит по УЖЕ СУЩЕСТВУЮЩЕЙ сущности. "
        "Если видишь такой тег — просто скопируй N в соответствующее *_id поле, "
        "ничего не резолвь и не выдумывай.\n"
        "Любое название БЕЗ такого тега (обычный текст) — это title НОВОЙ сущности, "
        "которую нужно создать (create_quest/create_questline/новый шаг). "
        "Если голый текст совпадает с title, который создаётся ДРУГИМ action'ом в "
        "ЭТОМ ЖЕ списке — это ссылка на него: используй questline_id_ref/quest_id_ref "
        "с индексом создающего action'а, а НЕ questline_id/quest_id и НЕ "
        "questline/category (те поля — только для имени НОВОГО объекта при его "
        "создании или для резолва имени уже существующего объекта по подстроке).\n"
        "Действия и когда их использовать:\n"
        "  • create_questline — создать новый квестлайн. title обязателен.\n"
        "  • create_quest — создать НОВЫЙ квест с нуля. steps — только если "
        "пользователь явно перечислил шаги нового квеста. Если квест создаётся "
        "СРАЗУ ВНУТРИ квестлайна, который тоже создаётся в этом же запросе — "
        "ОБЯЗАТЕЛЬНО проставь questline_id_ref на индекс create_questline "
        "action'а, не забывай это поле.\n"
        "  • update_quest — изменить СУЩЕСТВУЮЩИЙ квест (обязателен quest_id из "
        "тега quest=N, или quest_id_ref если квест создаётся в этом же батче): "
        "статус, title, pinned, значимость, и ГЛАВНОЕ — прикрепление к квестлайну "
        "(questline_id из тега questline=N, questline_id_ref если квестлайн "
        "создаётся тут же, или questline как имя уже существующего для резолва "
        "по подстроке; clear_questline=true — отвязать).\n"
        "  • add_step — добавить НОВЫЙ шаг внутрь существующего квеста (quest_id "
        "из тега quest=N). title обязателен, steps не используется.\n"
        "  • update_step / delete_step — quest_id + step_id (оба из тегов).\n"
        "Примеры:\n"
        "  \"создай квестлайн Бэкапы и закинь туда quest=42\" →\n"
        "    [{index:0, action:create_questline, title:\"Бэкапы\"}, "
        "{index:1, action:update_quest, quest_id:42, questline_id_ref:0}]\n"
        "  \"перенеси quest=5 в questline=3, поставь completed\" →\n"
        "    [{index:0, action:update_quest, quest_id:5, questline_id:3, "
        "status:\"completed\"}]\n"
        "  \"quest=9 сделай completed и создай квестлайн Инфраструктура, закинь "
        "его туда\" →\n"
        "    [{index:0, action:update_quest, quest_id:9, status:\"completed\"}, "
        "{index:1, action:create_questline, title:\"Инфраструктура\"}, "
        "{index:2, action:update_quest, quest_id:9, questline_id_ref:1}]\n"
        "  \"создай квестлайн Мониторинг с квестом Настроить графану\" →\n"
        "    [{index:0, action:create_questline, title:\"Мониторинг\"}, "
        "{index:1, action:create_quest, title:\"Настроить графану\", "
        "questline_id_ref:0}]\n"
        "Верни ОДИН JSON-объект по схеме, без пояснений вне JSON. Поля, не нужные "
        "для конкретного action, оставляй null (clear_questline=false по "
        "умолчанию, steps=null кроме create_quest с явными шагами).\n"
        f"status один из: {statuses}.\n"
        "needs_clarification=true (actions=[]) только если запрос реально "
        "неоднозначен (непонятно, какой квест/шаг/квестлайн имеется в виду и "
        "тег/имя не помогает установить это однозначно).\n"
        "JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
