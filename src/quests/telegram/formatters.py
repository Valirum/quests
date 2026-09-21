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
    ql = (q.get("questline_title") or "").strip()
    if ql or q.get("questline_id") is not None:
        lid = q.get("questline_id")
        if ql and lid is not None:
            lines.append(f"Квестлайн: {ql} (questline={lid})")
        elif ql:
            lines.append(f"Квестлайн: {ql}")
        else:
            lines.append(f"Квестлайн: questline={lid}")
    lines.append(f"Прогресс: {q.get('progress_label') or '—'}")
    lines.append(f"Срок: {_fmt_deadline(q)}")
    steps = q.get("steps") or []
    if steps:
        lines.append("Шаги:")
        for s in steps[:12]:
            mark = "✓" if s.get("done") else "·"
            sid = s.get("id")
            step_ref = f" · step={sid}" if sid is not None else ""
            lines.append(
                f"  {mark} {s.get('title')} "
                f"({s.get('progress_current')}/{s.get('progress_total')}){step_ref}"
            )
        if len(steps) > 12:
            lines.append(f"  … ещё {len(steps) - 12}")
    desc = (q.get("description") or "").strip()
    if desc:
        lines.append("")
        lines.append(desc[:500])
    return "\n".join(lines)


def format_active_by_questline(quests: list[dict]) -> str:
    """Group active quests: category → questline → quests."""
    if not quests:
        return "Активных задач нет."

    cats: dict[str, dict[str, tuple[str, list[dict]]]] = {}
    cat_order: list[str] = []
    for q in quests:
        cat = (q.get("category_label") or "").strip() or "Без раздела"
        if cat not in cats:
            cats[cat] = {}
            cat_order.append(cat)
        lid = q.get("questline_id")
        if lid is None:
            line_key = ""
            line_title = "Без квестлайна"
        else:
            line_key = str(int(lid))
            line_title = (q.get("questline_title") or "").strip() or f"questline={lid}"
        bucket = cats[cat]
        if line_key not in bucket:
            bucket[line_key] = (line_title, [])
        bucket[line_key][1].append(q)

    chunks: list[str] = [f"<b>Активные · {len(quests)}</b>"]
    for cat in cat_order:
        chunks.append("")
        chunks.append(f"<b>{cat}</b>")
        lines_map = cats[cat]
        keys = sorted(
            lines_map.keys(),
            key=lambda k: (k != "", lines_map[k][0].lower()),
        )
        for key in keys:
            title, items = lines_map[key]
            if key:
                chunks.append(f"  <i>{title}</i> · questline={key}")
            else:
                chunks.append(f"  <i>{title}</i>")
            for q in items:
                chunks.append("    " + format_quest_line(q))
    return "\n".join(chunks)


def format_active_by_category(quests: list[dict]) -> str:
    return format_active_by_questline(quests)
