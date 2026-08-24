"""LLM settings — Groq (default), Cursor Agent API, or optional Ollama."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PROVIDER = "groq"
DEFAULT_CURSOR_MODEL = "composer-2.5"
DEFAULT_GROQ_BASE = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT = 180.0


@dataclass(frozen=True)
class LlmSettings:
    provider: str  # "groq" | "cursor" | "ollama"
    api_key: str  # CURSOR_API_KEY for cursor, GROQ_API_KEY for groq
    model: str
    base_url: str  # groq / ollama only
    timeout: float
    temperature: float = 0.1
    proxy: str = ""  # groq only — Groq blocks some regions; route via HTTP(S) proxy


def load_llm_settings() -> LlmSettings:
    provider = (
        os.environ.get("QUESTS_LLM_PROVIDER") or DEFAULT_PROVIDER
    ).strip().lower()
    if provider not in {"cursor", "ollama", "groq"}:
        provider = DEFAULT_PROVIDER

    if provider == "cursor":
        api_key = (
            os.environ.get("QUESTS_CURSOR_API_KEY")
            or os.environ.get("CURSOR_API_KEY")
            or ""
        ).strip()
        model = (
            os.environ.get("QUESTS_LLM_MODEL") or DEFAULT_CURSOR_MODEL
        ).strip()
        base = ""
    elif provider == "groq":
        api_key = (
            os.environ.get("QUESTS_GROQ_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or ""
        ).strip()
        model = (
            os.environ.get("QUESTS_LLM_MODEL") or DEFAULT_GROQ_MODEL
        ).strip()
        base = (os.environ.get("QUESTS_LLM_BASE") or DEFAULT_GROQ_BASE).rstrip("/")
    else:
        api_key = ""
        model = (
            os.environ.get("QUESTS_LLM_MODEL") or DEFAULT_OLLAMA_MODEL
        ).strip()
        base = (os.environ.get("QUESTS_LLM_BASE") or DEFAULT_OLLAMA_BASE).rstrip(
            "/"
        )

    proxy = ""
    if provider == "groq":
        proxy = (
            os.environ.get("QUESTS_LLM_PROXY")
            or os.environ.get("QUESTS_TG_PROXY")
            or ""
        ).strip()

    return LlmSettings(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base,
        timeout=float(os.environ.get("QUESTS_LLM_TIMEOUT") or DEFAULT_TIMEOUT),
        temperature=float(os.environ.get("QUESTS_LLM_TEMPERATURE") or "0.1"),
        proxy=proxy,
    )
