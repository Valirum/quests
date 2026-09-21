"""Local LLM helpers (legacy single-quest draft).

The Telegram bot and web «Команда» now share Go action-batch
(go/internal/llmassist via /api/llm/actions/*). This package remains for
`quests llm-add` / older draft tooling until that CLI is switched too.
"""

from __future__ import annotations

from quests.llm.client import LlmError, extract_quest_draft, extract_quest_draft_sync
from quests.llm.draft import draft_to_create_body, format_draft_preview
from quests.llm.schema import QuestDraft, QuestDraftBundle

__all__ = [
    "LlmError",
    "QuestDraft",
    "QuestDraftBundle",
    "draft_to_create_body",
    "extract_quest_draft",
    "extract_quest_draft_sync",
    "format_draft_preview",
]
