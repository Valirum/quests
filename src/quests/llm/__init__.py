"""Local LLM helpers: free-form text → structured quest draft.

The action-batch assistant (text -> quest CRUD) lives in Go now
(go/internal/llmassist) — this package keeps only the single-quest draft
path used by the Telegram bot's /new-llm and `quests llm-add`.
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
