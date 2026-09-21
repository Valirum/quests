"""Format LLM action-batch preview for Telegram HTML."""

from __future__ import annotations

from html import escape
from typing import Any

_ACTION_RU = {
    "create_questline": "создать квестлайн",
    "create_quest": "создать квест",
    "add_step": "добавить шаг",
    "update_step": "изменить шаг",
    "delete_step": "удалить шаг",
    "update_quest": "изменить квест",
}


def _esc(s: Any) -> str:
    return escape(str(s or ""), quote=False)


def format_actions_preview(
    batch: dict[str, Any],
    preview: list[dict[str, Any]] | None = None,
) -> str:
    """Human-readable plan from ActionBatch (+ optional dry-run rows)."""
    actions = list((batch or {}).get("actions") or [])
    rows = list(preview or [])
    by_index = {int(r.get("index", -1)): r for r in rows}

    lines = ["<b>План действий</b>"]
    if not actions:
        lines.append("<i>(пусто)</i>")
        return "\n".join(lines)

    for act in actions:
        idx = int(act.get("index", 0))
        kind = str(act.get("action") or "?")
        label = _ACTION_RU.get(kind, kind)
        title = act.get("title")
        bits = [f"<b>{idx + 1}.</b> {label}"]
        if title:
            bits.append(f"«{_esc(title)}»")
        if act.get("quest_id") is not None:
            bits.append(f"quest={act['quest_id']}")
        if act.get("questline_id") is not None:
            bits.append(f"questline={act['questline_id']}")
        if act.get("step_id") is not None:
            bits.append(f"step={act['step_id']}")
        if act.get("category") or act.get("category_id") is not None:
            cat = act.get("category") or f"id={act.get('category_id')}"
            bits.append(f"раздел={_esc(cat)}")
        if act.get("status"):
            bits.append(f"статус={_esc(act['status'])}")
        if act.get("questline_id_ref") is not None:
            bits.append(f"→квестлайн[{act['questline_id_ref']}]")
        if act.get("quest_id_ref") is not None:
            bits.append(f"→квест[{act['quest_id_ref']}]")
        lines.append(" ".join(bits))

        pr = by_index.get(idx)
        if pr and pr.get("is_new"):
            after = pr.get("after") or {}
            aid = after.get("id")
            if aid is not None:
                lines.append(f"   <i>новый id≈{aid}</i>")
        steps = act.get("steps") or []
        if steps:
            for st in steps[:8]:
                lines.append(f"   · {_esc(st.get('title') or 'шаг')}")
            if len(steps) > 8:
                lines.append(f"   · … ещё {len(steps) - 8}")

    lines.append("")
    lines.append("Применить этот план?")
    return "\n".join(lines)


def history_to_prompt_text(
    user_text: str,
    history: list[tuple[str, str]] | None,
) -> str:
    """Fold clarify turns into one user message (Go preview has no history yet)."""
    if not history:
        return user_text.strip()
    parts: list[str] = ["Предыдущий диалог:"]
    for role, content in history:
        r = "пользователь" if role == "user" else "ассистент"
        parts.append(f"{r}: {content}")
    parts.append("")
    parts.append("Текущий запрос:")
    parts.append(user_text.strip())
    return "\n".join(parts)
