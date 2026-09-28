"""Extract QuestDraft via Groq (default) or Ollama."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from pydantic import ValidationError

from quests.llm.config import LlmSettings, load_llm_settings
from quests.llm.schema import (
    QuestDraft,
    QuestDraftBundle,
    quest_draft_json_schema,
    system_prompt,
)

log = logging.getLogger("quests.llm")


class LlmError(Exception):
    pass


def _tz() -> ZoneInfo:
    name = os.environ.get("QUESTS_TZ") or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def _now_context() -> tuple[str, str]:
    tz = _tz()
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M %A"), str(tz)


def _parse_draft(raw: str | dict[str, Any]) -> QuestDraftBundle:
    if isinstance(raw, dict):
        data = raw
    else:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        # Agent sometimes wraps JSON in prose — take first {...} blob.
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LlmError(f"модель вернула не-JSON: {e}") from e
    if not isinstance(data, dict):
        raise LlmError("модель вернула не объект JSON")

    # Legacy: single QuestDraft without variations wrapper.
    if "variations" not in data and "title" in data:
        try:
            one = QuestDraft.model_validate(data)
        except ValidationError as e:
            raise LlmError(f"черновик не прошёл валидацию: {e}") from e
        return QuestDraftBundle(
            needs_clarification=bool(one.needs_clarification),
            clarify_question=one.clarify_question or "",
            variations=[one],
        )

    try:
        return QuestDraftBundle.model_validate(data)
    except ValidationError as e:
        raise LlmError(f"черновик не прошёл валидацию: {e}") from e


def _build_ollama_messages(
    user_text: str,
    *,
    history: list[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    local, tz_name = _now_context()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt(now_local=local, tz_name=tz_name)},
    ]
    for role, content in history or []:
        if role in {"user", "assistant"} and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text.strip()})
    return messages


def _groq_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "quest_draft_bundle",
            "schema": quest_draft_json_schema(),
        },
    }


def _extract_groq_sync(
    user_text: str,
    *,
    settings: LlmSettings,
    history: list[tuple[str, str]] | None,
) -> QuestDraftBundle:
    import urllib.error
    import urllib.request

    if not settings.api_key:
        raise LlmError(
            "нужен GROQ_API_KEY или QUESTS_GROQ_API_KEY (console.groq.com → API Keys)"
        )

    payload = {
        "model": settings.model,
        "messages": _build_ollama_messages(user_text, history=history),
        "temperature": settings.temperature,
        "response_format": _groq_response_format(),
    }
    url = f"{settings.base_url}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.api_key}",
            # Cloudflare in front of api.groq.com bans the default
            # "Python-urllib/…" UA outright (403 browser_signature_banned).
            "User-Agent": "quests-bot/1.0",
        },
        method="POST",
    )
    # Cloudflare also blocks some regions at the network edge — route
    # through settings.proxy (QUESTS_LLM_PROXY / QUESTS_TG_PROXY) when set,
    # same as the Telegram client.
    opener = (
        urllib.request.build_opener(
            urllib.request.ProxyHandler(
                {"http": settings.proxy, "https": settings.proxy}
            )
        )
        if settings.proxy
        else urllib.request.build_opener()
    )
    try:
        with opener.open(req, timeout=settings.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise LlmError(f"Groq HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LlmError(f"не удалось связаться с Groq: {e.reason}") from e

    choices = data.get("choices") or [] if isinstance(data, dict) else []
    content = (choices[0].get("message") or {}).get("content") if choices else None
    if content is None:
        raise LlmError(f"пустой ответ Groq: {data!r}"[:300])
    return _parse_draft(content)


def _extract_ollama_sync(
    user_text: str,
    *,
    settings: LlmSettings,
    history: list[tuple[str, str]] | None,
) -> QuestDraftBundle:
    import urllib.error
    import urllib.request

    payload = {
        "model": settings.model,
        "messages": _build_ollama_messages(user_text, history=history),
        "stream": False,
        "format": quest_draft_json_schema(),
        "options": {"temperature": settings.temperature},
    }
    url = f"{settings.base_url}/api/chat"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise LlmError(f"LLM HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise LlmError(
            f"не удалось связаться с Ollama ({settings.base_url}): {e.reason}"
        ) from e

    message = (data.get("message") or {}) if isinstance(data, dict) else {}
    content = message.get("content")
    if content is None:
        raise LlmError(f"пустой ответ LLM: {data!r}"[:300])
    return _parse_draft(content)


def extract_quest_draft_sync(
    user_text: str,
    *,
    settings: LlmSettings | None = None,
    history: list[tuple[str, str]] | None = None,
) -> QuestDraftBundle:
    settings = settings or load_llm_settings()
    if not user_text.strip():
        raise LlmError("пустой текст")
    if settings.provider == "groq":
        return _extract_groq_sync(user_text, settings=settings, history=history)
    return _extract_ollama_sync(user_text, settings=settings, history=history)


async def extract_quest_draft(
    user_text: str,
    *,
    settings: LlmSettings | None = None,
    history: list[tuple[str, str]] | None = None,
    session: aiohttp.ClientSession | None = None,
) -> QuestDraftBundle:
    """Async entry — Groq/Ollama use aiohttp."""
    settings = settings or load_llm_settings()
    if not user_text.strip():
        raise LlmError("пустой текст")

    if settings.provider == "groq":
        if not settings.api_key:
            raise LlmError(
                "нужен GROQ_API_KEY или QUESTS_GROQ_API_KEY "
                "(console.groq.com → API Keys)"
            )
        payload: dict[str, Any] = {
            "model": settings.model,
            "messages": _build_ollama_messages(user_text, history=history),
            "temperature": settings.temperature,
            "response_format": _groq_response_format(),
        }
        url = f"{settings.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "User-Agent": "quests-bot/1.0",
        }
        error_label = "Groq"
        proxy = settings.proxy or None
    else:
        payload = {
            "model": settings.model,
            "messages": _build_ollama_messages(user_text, history=history),
            "stream": False,
            "format": quest_draft_json_schema(),
            "options": {"temperature": settings.temperature},
        }
        url = f"{settings.base_url}/api/chat"
        headers = {}
        error_label = "Ollama"
        proxy = None

    owns = session is None
    session = session or aiohttp.ClientSession()
    try:
        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=settings.timeout),
            ) as resp:
                body = await resp.read()
                if resp.status >= 400:
                    raise LlmError(
                        f"{error_label} HTTP {resp.status}: "
                        f"{body.decode('utf-8', errors='replace')[:400]}"
                    )
                data = json.loads(body.decode("utf-8"))
        except aiohttp.ClientError as e:
            raise LlmError(
                f"не удалось связаться с {error_label} ({settings.base_url}): {e}"
            ) from e
    finally:
        if owns:
            await session.close()

    if settings.provider == "groq":
        choices = data.get("choices") or [] if isinstance(data, dict) else []
        content = (
            (choices[0].get("message") or {}).get("content") if choices else None
        )
    else:
        message = (data.get("message") or {}) if isinstance(data, dict) else {}
        content = message.get("content")
    if content is None:
        raise LlmError(f"пустой ответ {error_label}: {data!r}"[:300])
    return _parse_draft(content)
