"""Convert QuestDraft → API create body + human preview."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from quests.llm.schema import QuestDraft
from quests.models import SIGNIFICANCE_LABEL_RU
from quests.timeutil import format_remaining, to_utc_iso


def resolve_category_id(
    categories: list[dict[str, Any]], slug: str | None
) -> int | None:
    if not slug:
        return None
    for c in categories:
        if str(c.get("slug") or "").lower() == slug.lower():
            return int(c["id"])
    return None


def _tz() -> ZoneInfo:
    name = os.environ.get("QUESTS_TZ") or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def _resolve_timing(
    draft: QuestDraft,
) -> tuple[int | None, int | None]:
    deadline_m = draft.deadline_in_minutes
    duration_m = draft.duration_minutes
    if deadline_m is None and duration_m is not None:
        deadline_m = duration_m
    if duration_m is None and deadline_m is not None:
        # Same as API ``normalize_quest_deadline``: min(24h, time-to-deadline).
        duration_m = min(24 * 60, int(deadline_m))
    if deadline_m is not None and duration_m is not None:
        duration_m = min(int(duration_m), int(deadline_m))
    return deadline_m, duration_m


def draft_to_create_body(
    draft: QuestDraft,
    *,
    categories: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build POST /api/quests JSON from a draft."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    body: dict[str, Any] = {
        "title": draft.title,
        "description": draft.description or "",
        "status": "active",
        "significance": draft.significance,
        "pinned": bool(draft.pinned),
    }

    cat_id = resolve_category_id(categories or [], draft.category_slug)
    if cat_id is not None:
        body["category_id"] = cat_id

    deadline_m, duration_m = _resolve_timing(draft)

    if deadline_m is not None:
        deadline = now + timedelta(minutes=int(deadline_m))
        body["deadline_at"] = to_utc_iso(deadline)
        body["duration_seconds"] = max(60, int(duration_m or deadline_m) * 60)

    steps = draft.steps
    if not steps:
        steps = [draft.title]
    body["steps"] = [
        {
            "title": t,
            "progress_current": 0,
            "progress_total": 1,
            "sort_order": i,
        }
        for i, t in enumerate(steps)
    ]
    return body


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_draft_preview(
    draft: QuestDraft,
    *,
    html: bool = False,
    now: datetime | None = None,
    index: int | None = None,
    total: int | None = None,
) -> str:
    sig = SIGNIFICANCE_LABEL_RU.get(draft.significance, draft.significance)
    cat = draft.category_slug or "—"

    deadline_m, duration_m = _resolve_timing(draft)
    tz = _tz()
    now_local = now.astimezone(tz) if now is not None else datetime.now(tz)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=tz)

    if deadline_m:
        deadline_at = now_local + timedelta(minutes=int(deadline_m))
        deadline_label = deadline_at.strftime("%d.%m.%Y %H:%M")
        window_label = format_remaining(int(duration_m or deadline_m) * 60)
        timing_lines = [
            f"Срок: {deadline_label}",
            f"Окно: {window_label}",
        ]
    else:
        timing_lines = ["Срок: без срока"]

    steps = draft.steps or [draft.title]
    if index is not None and total is not None and total > 1:
        header = f"Вариант {index + 1}/{total}"
    else:
        header = "Черновик"

    if html:
        lines = [
            f"<b>{_esc(header)}</b>",
            f"<b>{_esc(draft.title)}</b>",
            f"Раздел: <code>{_esc(cat)}</code> · {_esc(sig)}",
            *[f"{_esc(t)}" for t in timing_lines],
            "Шаги:",
            *[f"  · {_esc(s)}" for s in steps],
        ]
        if draft.description:
            lines.append("")
            lines.append(_esc(draft.description))
        return "\n".join(lines)

    lines = [
        f"{header}: {draft.title}",
        f"  раздел: {cat}  значимость: {sig}",
        *[f"  {t}" for t in timing_lines],
        "  шаги:",
        *[f"    · {s}" for s in steps],
    ]
    if draft.description:
        lines.append(f"  описание: {draft.description}")
    return "\n".join(lines)
