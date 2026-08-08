"""Extract QuestDraft via Cursor Agent API (default) or Ollama."""

from __future__ import annotations

import asyncio
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


def _user_block(user_text: str, history: list[tuple[str, str]] | None) -> str:
    parts: list[str] = []
    for role, content in history or []:
        if role in {"user", "assistant"} and content.strip():
            parts.append(f"{role.upper()}: {content.strip()}")
    parts.append(f"USER: {user_text.strip()}")
    return "\n\n".join(parts)


def _full_prompt(user_text: str, history: list[tuple[str, str]] | None) -> str:
    local, tz_name = _now_context()
    return (
        f"{system_prompt(now_local=local, tz_name=tz_name)}\n\n"
        f"Ввод:\n{_user_block(user_text, history)}"
    )


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


def _extract_cursor_sync(
    user_text: str,
    *,
    settings: LlmSettings,
    history: list[tuple[str, str]] | None,
) -> QuestDraftBundle:
    from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CursorAgentError

    if not settings.api_key:
        raise LlmError(
            "нужен CURSOR_API_KEY или QUESTS_CURSOR_API_KEY "
            "(Dashboard → Integrations / API Keys)"
        )

    prompt = _full_prompt(user_text, history)
    try:
        # Cloud, без репо — пустой workspace, только текст→JSON.
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=settings.api_key,
                model=settings.model,
                cloud=CloudAgentOptions(),
            ),
        )
    except CursorAgentError as e:
        raise LlmError(f"Cursor API: {e}") from e

    status = getattr(result.status, "value", result.status)
    if str(status) != "finished":
        raise LlmError(
            f"Cursor agent status={status!r} id={result.id} "
            f"text={(result.result or '')[:200]!r}"
        )

    content = (result.result or "").strip()
    if not content:
        raise LlmError(f"пустой ответ Cursor agent (run={result.id})")
    bundle = _parse_draft(content)
    draft = bundle.primary
    log.info(
        "cursor draft title=%r variants=%s cat=%s clarify=%s run=%s",
        draft.title,
        len(bundle.variations),
        draft.category_slug,
        bundle.needs_clarification,
        result.id,
    )
    return bundle


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
    if settings.provider == "ollama":
        return _extract_ollama_sync(user_text, settings=settings, history=history)
    return _extract_cursor_sync(user_text, settings=settings, history=history)


async def extract_quest_draft(
    user_text: str,
    *,
    settings: LlmSettings | None = None,
    history: list[tuple[str, str]] | None = None,
    session: aiohttp.ClientSession | None = None,
) -> QuestDraftBundle:
    """Async entry — Cursor runs in a worker thread; Ollama uses aiohttp."""
    settings = settings or load_llm_settings()
    if not user_text.strip():
        raise LlmError("пустой текст")

    if settings.provider == "cursor":
        return await asyncio.to_thread(
            _extract_cursor_sync,
            user_text,
            settings=settings,
            history=history,
        )

    # ollama path
    payload = {
        "model": settings.model,
        "messages": _build_ollama_messages(user_text, history=history),
        "stream": False,
        "format": quest_draft_json_schema(),
        "options": {"temperature": settings.temperature},
    }
    url = f"{settings.base_url}/api/chat"
    owns = session is None
    session = session or aiohttp.ClientSession()
    try:
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=settings.timeout),
            ) as resp:
                body = await resp.read()
                if resp.status >= 400:
                    raise LlmError(
                        f"LLM HTTP {resp.status}: "
                        f"{body.decode('utf-8', errors='replace')[:400]}"
                    )
                data = json.loads(body.decode("utf-8"))
        except aiohttp.ClientError as e:
            raise LlmError(
                f"не удалось связаться с Ollama ({settings.base_url}): {e}"
            ) from e
    finally:
        if owns:
            await session.close()

    message = (data.get("message") or {}) if isinstance(data, dict) else {}
    content = message.get("content")
    if content is None:
        raise LlmError(f"пустой ответ LLM: {data!r}"[:300])
    return _parse_draft(content)
