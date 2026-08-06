"""Format quest cards and list messages for Telegram."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quests.timeutil import ensure_utc, format_remaining

STATUS_RU = {
    "active": "активно",
    "delayed": "просрочено",
    "completed": "выполнено",
    "failed": "провал",
    "archived": "архив",
}


def status_label(status: Any) -> str:
    key = status.value if hasattr(status, "value") else str(status or "")
    return STATUS_RU.get(key, key or "?")


def _fmt_deadline(q: dict) -> str:
    rem = q.get("remaining_seconds")
    if rem is not None:
        return f"осталось {format_remaining(int(rem))}"
    raw = q.get("deadline_at")
    if not raw:
        return "без срока"
    try:
        dt = ensure_utc(datetime.fromisoformat(str(raw)))
        if dt is None:
            return str(raw)
        return dt.strftime("%d.%m %H:%M UTC")
    except ValueError:
        return str(raw)


def format_quest_line(q: dict) -> str:
    pin = "📌 " if q.get("pinned") else ""
    qid = q.get("id")
    title = q.get("title") or "?"
    progress = q.get("progress_label") or ""
    timer = ""
    if q.get("deadline_at") and q.get("remaining_seconds") is not None:
        timer = f" · {_fmt_deadline(q)}"
    return f"{pin}#{qid} {title} ({progress}){timer}"


def format_quest_card(q: dict) -> str:
    lines = [
        f"<b>#{q.get('id')} · {q.get('title') or '?'}</b>",
        f"Статус: {status_label(q.get('status'))}",
    ]
    cat = q.get("category_label")
    if cat:
        lines.append(f"Раздел: {cat}")
    elif q.get("category_slug"):
        lines.append(f"Раздел: {q.get('category_slug')}")
    lines.append(f"Прогресс: {q.get('progress_label') or '—'}")
    lines.append(f"Срок: {_fmt_deadline(q)}")
    steps = q.get("steps") or []
    if steps:
        lines.append("Шаги:")
        for s in steps[:12]:
            mark = "✓" if s.get("done") else "·"
            lines.append(
                f"  {mark} {s.get('title')} "
                f"({s.get('progress_current')}/{s.get('progress_total')})"
            )
        if len(steps) > 12:
            lines.append(f"  … ещё {len(steps) - 12}")
    desc = (q.get("description") or "").strip()
    if desc:
        lines.append("")
        lines.append(desc[:500])
    return "\n".join(lines)


def format_active_by_category(quests: list[dict]) -> str:
    if not quests:
        return "Активных задач нет."

    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for q in quests:
        label = (q.get("category_label") or "").strip() or "Без раздела"
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(q)

    chunks: list[str] = [f"<b>Активные · {len(quests)}</b>"]
    for label in order:
        chunks.append("")
        chunks.append(f"<b>{label}</b>")
        for q in groups[label]:
            chunks.append(format_quest_line(q))
    return "\n".join(chunks)
