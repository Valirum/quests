"""Quests CLI — quest CRUD via local API + local hook management.

Usage::

    quests --help
    quests list --json
    quests hook add --event complete --type script --command 'notify-send "$QUESTS_TITLE"'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from quests import hooks as hooks_mod
from quests.config import HOST, PORT

API_BASE = (os.environ.get("QUESTS_API") or f"http://{HOST}:{PORT}").rstrip("/")


# ── output ───────────────────────────────────────────────────────────────────


class CliError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def _want_json(ns: argparse.Namespace) -> bool:
    return bool(getattr(ns, "json", False))


def emit(data: Any, *, as_json: bool, text: str | None = None) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    elif text is not None:
        print(text)
    else:
        print(data)


def emit_error(message: str, *, as_json: bool, code: int = 1) -> int:
    if as_json:
        print(
            json.dumps({"ok": False, "error": message}, ensure_ascii=False),
            file=sys.stderr,
        )
    else:
        print(f"error: {message}", file=sys.stderr)
    return code


# ── API ──────────────────────────────────────────────────────────────────────


def api_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> Any:
    url = f"{API_BASE}{path}"
    if query:
        q = {k: v for k, v in query.items() if v is not None}
        if q:
            url = f"{url}?{urllib.parse.urlencode(q)}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = parsed.get("detail", detail)
        except json.JSONDecodeError:
            pass
        raise CliError(f"API {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise CliError(
            f"не удалось связаться с API ({API_BASE}): {e.reason}. "
            "Запусти сервер: ./scripts/run-server.sh"
        ) from e


def _status_val(q: dict[str, Any]) -> str:
    s = q.get("status")
    return s.value if hasattr(s, "value") else str(s or "")


def _fmt_quest_line(q: dict[str, Any]) -> str:
    pin = "★" if q.get("pinned") else " "
    qid = q.get("id")
    title = q.get("title") or "?"
    status = _status_val(q)
    progress = q.get("progress_label") or ""
    cat = q.get("category_slug") or q.get("category_label") or ""
    line = q.get("questline_title") or ""
    extras = []
    if cat:
        extras.append(cat)
    if line:
        extras.append(f"⟶{line}")
    suffix = f"  [{', '.join(extras)}]" if extras else ""
    return f"{pin} {qid:>4}  {status:<10}  {progress:<8}  {title}{suffix}"


def _fmt_quest_detail(q: dict[str, Any]) -> str:
    lines = [
        f"#{q.get('id')}  {q.get('title')}",
        f"  status:       {_status_val(q)}",
        f"  significance: {q.get('significance')}",
        f"  pinned:       {bool(q.get('pinned'))}",
        f"  progress:     {q.get('progress_label')}",
    ]
    cat_bits = []
    if q.get("category_id") is not None:
        cat_bits.append(f"id={q.get('category_id')}")
    if q.get("category_slug"):
        cat_bits.append(str(q.get("category_slug")))
    if q.get("category_label"):
        cat_bits.append(str(q.get("category_label")))
    lines.append(f"  category:     {(' '.join(cat_bits) if cat_bits else '—')}")
    if q.get("questline_id") is not None:
        ql = q.get("questline_title") or ""
        lines.append(f"  questline:    #{q.get('questline_id')} {ql}".rstrip())
    else:
        lines.append("  questline:    —")
    if q.get("deadline_at"):
        lines.append(f"  deadline:     {q.get('deadline_at')}")
    if q.get("description"):
        lines.append(f"  description:  {q.get('description')}")
    steps = q.get("steps") or []
    if steps:
        lines.append("  steps:")
        for s in steps:
            mark = "✓" if s.get("done") else "·"
            lines.append(
                f"    {mark} [{s.get('id')}] {s.get('title')}  "
                f"{s.get('progress_current')}/{s.get('progress_total')}"
            )
    return "\n".join(lines)


def _resolve_category_id(raw: str | None) -> int | None:
    """Accept id, slug, label, or none/-/null to clear."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "" or text.lower() in {"none", "-", "null", "нет"}:
        return None
    if text.isdigit():
        return int(text)
    cats = api_request("GET", "/api/categories") or []
    needle = text.lower()
    for c in cats:
        if str(c.get("slug") or "").lower() == needle:
            return int(c["id"])
        if str(c.get("label") or "").lower() == needle:
            return int(c["id"])
    raise CliError(f"категория не найдена: {raw!r} (id|slug|label|none)")


def _resolve_questline_id(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "" or text.lower() in {"none", "-", "null", "нет"}:
        return None
    if text.isdigit():
        return int(text)
    lines = api_request("GET", "/api/questlines") or []
    needle = text.lower()
    matches = [l for l in lines if needle in str(l.get("title") or "").lower()]
    if not matches:
        raise CliError(f"квестлайн не найден: {raw!r}")
    if len(matches) > 1:
        ids = ", ".join(f"#{m['id']} {m.get('title')}" for m in matches)
        raise CliError(f"несколько квестлайнов: {ids}; укажи id")
    return int(matches[0]["id"])


def _fmt_category_line(c: dict[str, Any]) -> str:
    return (
        f"{c.get('id'):>3}  {c.get('slug'):<10}  {c.get('label'):<14}  "
        f"{c.get('color') or ''}  ord={c.get('sort_order')}"
    )


def _fmt_questline_line(l: dict[str, Any]) -> str:
    cat = l.get("category_slug") or l.get("category_label") or "—"
    return (
        f"{l.get('id'):>3}  {l.get('icon') or 'document':<8}  "
        f"{l.get('color') or '#9a9a9a':<8}  [{cat}]  {l.get('title')}"
    )


def _fmt_questline_detail(l: dict[str, Any]) -> str:
    cat = l.get("category_label") or l.get("category_slug") or "—"
    lines = [
        f"#{l.get('id')}  {l.get('title')}",
        f"  category:  {cat}"
        + (f" (id={l.get('category_id')})" if l.get("category_id") is not None else ""),
        f"  color:     {l.get('color')}",
        f"  icon:      {l.get('icon')}",
    ]
    if l.get("description"):
        lines.append(f"  description: {l.get('description')}")
    return "\n".join(lines)


def _fmt_hook_line(h: dict[str, Any] | hooks_mod.Hook) -> str:
    d = h.to_dict() if isinstance(h, hooks_mod.Hook) else h
    scope = f"quest:{d['quest_id']}" if d.get("quest_id") is not None else "global"
    on = "on " if d.get("enabled", True) else "off"
    ev = ",".join(d.get("events") or [])
    target = d.get("command") or d.get("url") or d.get("path") or ""
    name = d.get("name") or ""
    label = f"{d.get('id')}" + (f" ({name})" if name else "")
    return f"{on}  {label:<20}  {scope:<10}  {d.get('type'):<8}  [{ev}]  {target}"


# ── quest commands ───────────────────────────────────────────────────────────


def cmd_list(ns: argparse.Namespace) -> int:
    query: dict[str, Any] = {}
    if ns.status:
        query["status"] = ns.status
    if ns.pinned:
        query["pinned"] = "true"
    elif ns.unpinned:
        query["pinned"] = "false"
    items = api_request("GET", "/api/quests", query=query) or []
    if getattr(ns, "category", None):
        cat_id = _resolve_category_id(ns.category)
        items = [q for q in items if q.get("category_id") == cat_id]
    if getattr(ns, "questline", None):
        ql_id = _resolve_questline_id(ns.questline)
        items = [q for q in items if q.get("questline_id") == ql_id]
    if _want_json(ns):
        emit(items, as_json=True)
        return 0
    if not items:
        print("(пусто)")
        return 0
    for q in items:
        print(_fmt_quest_line(q))
    return 0


def cmd_show(ns: argparse.Namespace) -> int:
    q = api_request("GET", f"/api/quests/{ns.quest_id}")
    if _want_json(ns):
        emit(q, as_json=True)
    else:
        print(_fmt_quest_detail(q))
    return 0


def cmd_add(ns: argparse.Namespace) -> int:
    body: dict[str, Any] = {
        "title": ns.title,
        "description": ns.description or "",
        "pinned": bool(ns.pin),
        "status": ns.status or "active",
        "significance": ns.significance or "common",
    }
    if getattr(ns, "category", None) is not None:
        body["category_id"] = _resolve_category_id(ns.category)
    if getattr(ns, "questline", None) is not None:
        body["questline_id"] = _resolve_questline_id(ns.questline)
    if ns.step:
        body["steps"] = [{"title": s, "progress_current": 0, "progress_total": 1} for s in ns.step]
    q = api_request("POST", "/api/quests", body=body)
    if _want_json(ns):
        emit(q, as_json=True)
    else:
        print(f"создан #{q['id']}: {q['title']}")
    return 0


def cmd_llm_add(ns: argparse.Namespace) -> int:
    """Free-form text → local LLM draft → POST /api/quests."""
    from quests.llm import (
        LlmError,
        draft_to_create_body,
        extract_quest_draft_sync,
        format_draft_preview,
    )
    from quests.llm.config import load_llm_settings

    text = " ".join(ns.text).strip() if isinstance(ns.text, list) else str(ns.text).strip()
    if not text:
        raise CliError("нужен текст описания")

    settings = load_llm_settings()
    if not _want_json(ns):
        if settings.provider == "cursor":
            print(
                f"Cursor ({settings.model})…",
                file=sys.stderr,
            )
        else:
            print(
                f"Ollama ({settings.model} @ {settings.base_url})…",
                file=sys.stderr,
            )
    try:
        bundle = extract_quest_draft_sync(text, settings=settings)
    except LlmError as e:
        raise CliError(str(e)) from e

    if bundle.needs_clarification and (bundle.clarify_question or "").strip():
        draft = bundle.primary
        if _want_json(ns):
            emit(
                {
                    "ok": False,
                    "needs_clarification": True,
                    "question": bundle.clarify_question,
                    "draft": draft.model_dump(),
                    "variations": [d.model_dump() for d in bundle.variations],
                },
                as_json=True,
            )
            return 2
        print(format_draft_preview(draft, index=0, total=len(bundle.variations)))
        print(f"\nуточнение: {bundle.clarify_question}", file=sys.stderr)
        return 2

    pick = max(0, int(getattr(ns, "variant", 0) or 0))
    pick = min(pick, len(bundle.variations) - 1)
    draft = bundle.variations[pick]
    cats = api_request("GET", "/api/categories") or []
    body = draft_to_create_body(draft, categories=cats)

    if not bool(getattr(ns, "yes", False)) and not _want_json(ns):
        for i, d in enumerate(bundle.variations):
            mark = "→ " if i == pick else "  "
            print(mark + format_draft_preview(d, index=i, total=len(bundle.variations)))
            print()
        try:
            ans = input(f"создать вариант {pick + 1}? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in {"y", "yes", "д", "да"}:
            print("отменено")
            return 1

    q = api_request("POST", "/api/quests", body=body)
    if _want_json(ns):
        emit(
            {
                "ok": True,
                "draft": draft.model_dump(),
                "variations": [d.model_dump() for d in bundle.variations],
                "picked": pick,
                "quest": q,
            },
            as_json=True,
        )
    else:
        print(f"создан #{q['id']}: {q['title']}")
    return 0


def cmd_set(ns: argparse.Namespace) -> int:
    body: dict[str, Any] = {}
    if ns.title is not None:
        body["title"] = ns.title
    if ns.description is not None:
        body["description"] = ns.description
    if ns.category is not None:
        body["category_id"] = _resolve_category_id(ns.category)
    if ns.questline is not None:
        body["questline_id"] = _resolve_questline_id(ns.questline)
    if ns.significance is not None:
        body["significance"] = ns.significance
    if not body:
        raise CliError("нечего менять: укажи --title/--description/--category/--questline/--significance")
    q = api_request("PATCH", f"/api/quests/{ns.quest_id}", body=body)
    if _want_json(ns):
        emit(q, as_json=True)
    else:
        print(_fmt_quest_detail(q))
    return 0


def cmd_pin(ns: argparse.Namespace) -> int:
    pinned = not bool(getattr(ns, "off", False))
    q = api_request("PATCH", f"/api/quests/{ns.quest_id}", body={"pinned": pinned})
    if _want_json(ns):
        emit(q, as_json=True)
    else:
        print(f"#{q['id']} pinned={q.get('pinned')}")
    return 0


def cmd_status(ns: argparse.Namespace) -> int:
    q = api_request("PATCH", f"/api/quests/{ns.quest_id}", body={"status": ns.status})
    if _want_json(ns):
        emit(q, as_json=True)
    else:
        print(f"#{q['id']} → {_status_val(q)}")
    return 0


def cmd_complete(ns: argparse.Namespace) -> int:
    ns.status = "completed"
    return cmd_status(ns)


def cmd_fail(ns: argparse.Namespace) -> int:
    ns.status = "failed"
    return cmd_status(ns)


def cmd_step(ns: argparse.Namespace) -> int:
    q = api_request("GET", f"/api/quests/{ns.quest_id}")
    steps = q.get("steps") or []
    if not steps:
        raise CliError("у квеста нет шагов")

    step = None
    if ns.step_id is not None:
        step = next((s for s in steps if int(s["id"]) == int(ns.step_id)), None)
        if step is None:
            raise CliError(f"шаг {ns.step_id} не найден")
    elif ns.title:
        needle = ns.title.lower()
        matches = [s for s in steps if needle in str(s.get("title") or "").lower()]
        if not matches:
            raise CliError(f"шаг с title≈{ns.title!r} не найден")
        if len(matches) > 1:
            ids = ", ".join(str(s["id"]) for s in matches)
            raise CliError(f"несколько шагов: {ids}; укажи --step-id")
        step = matches[0]
    else:
        # First open step, else last.
        open_steps = [s for s in steps if not s.get("done")]
        step = open_steps[0] if open_steps else steps[-1]

    cur = int(step.get("progress_current") or 0)
    total = max(1, int(step.get("progress_total") or 1))
    if ns.done:
        new_cur = total
    elif ns.set is not None:
        new_cur = int(ns.set)
    elif ns.inc is not None:
        new_cur = cur + int(ns.inc)
    else:
        new_cur = cur + 1

    updated = api_request(
        "PATCH",
        f"/api/quests/{ns.quest_id}/steps/{step['id']}",
        body={"progress_current": new_cur},
    )
    if _want_json(ns):
        emit(updated, as_json=True)
    else:
        st = next(s for s in updated["steps"] if s["id"] == step["id"])
        print(
            f"#{updated['id']} step [{st['id']}] {st['title']}: "
            f"{st['progress_current']}/{st['progress_total']}  ({updated.get('progress_label')})"
        )
    return 0


def cmd_delete(ns: argparse.Namespace) -> int:
    api_request("DELETE", f"/api/quests/{ns.quest_id}")
    if _want_json(ns):
        emit({"ok": True, "deleted": ns.quest_id}, as_json=True)
    else:
        print(f"удалён #{ns.quest_id}")
    return 0


# ── categories / questlines ──────────────────────────────────────────────────


def cmd_categories(ns: argparse.Namespace) -> int:
    items = api_request("GET", "/api/categories") or []
    if _want_json(ns):
        emit(items, as_json=True)
        return 0
    if not items:
        print("(пусто)")
        return 0
    for c in items:
        print(_fmt_category_line(c))
    return 0


def cmd_questline_list(ns: argparse.Namespace) -> int:
    items = api_request("GET", "/api/questlines") or []
    if getattr(ns, "category", None):
        cat_id = _resolve_category_id(ns.category)
        items = [l for l in items if l.get("category_id") == cat_id]
    if _want_json(ns):
        emit(items, as_json=True)
        return 0
    if not items:
        print("(пусто)")
        return 0
    for l in items:
        print(_fmt_questline_line(l))
    return 0


def cmd_questline_show(ns: argparse.Namespace) -> int:
    l = api_request("GET", f"/api/questlines/{ns.line_id}")
    if _want_json(ns):
        emit(l, as_json=True)
    else:
        print(_fmt_questline_detail(l))
    return 0


def cmd_questline_add(ns: argparse.Namespace) -> int:
    body: dict[str, Any] = {
        "title": ns.title,
        "description": ns.description or "",
        "color": ns.color or "#9a9a9a",
        "icon": ns.icon or "document",
    }
    if getattr(ns, "category", None) is not None:
        body["category_id"] = _resolve_category_id(ns.category)
    l = api_request("POST", "/api/questlines", body=body)
    if _want_json(ns):
        emit(l, as_json=True)
    else:
        print(f"создан квестлайн #{l['id']}: {l['title']}")
    return 0


def cmd_questline_set(ns: argparse.Namespace) -> int:
    body: dict[str, Any] = {}
    if ns.title is not None:
        body["title"] = ns.title
    if ns.description is not None:
        body["description"] = ns.description
    if ns.category is not None:
        body["category_id"] = _resolve_category_id(ns.category)
    if ns.color is not None:
        body["color"] = ns.color
    if ns.icon is not None:
        body["icon"] = ns.icon
    if not body:
        raise CliError("нечего менять: укажи --title/--description/--category/--color/--icon")
    l = api_request("PATCH", f"/api/questlines/{ns.line_id}", body=body)
    if _want_json(ns):
        emit(l, as_json=True)
    else:
        print(_fmt_questline_detail(l))
    return 0


def cmd_questline_delete(ns: argparse.Namespace) -> int:
    api_request("DELETE", f"/api/questlines/{ns.line_id}")
    if _want_json(ns):
        emit({"ok": True, "deleted": ns.line_id}, as_json=True)
    else:
        print(f"удалён квестлайн #{ns.line_id}")
    return 0


# ── hook commands ────────────────────────────────────────────────────────────


def cmd_hook_list(ns: argparse.Namespace) -> int:
    items = hooks_mod.load_hooks()
    if getattr(ns, "quest", None) is not None:
        items = [h for h in items if h.quest_id == ns.quest]
    elif getattr(ns, "global_only", False):
        items = [h for h in items if h.quest_id is None]
    data = [h.to_dict() for h in items]
    if _want_json(ns):
        emit(data, as_json=True)
        return 0
    if not data:
        print("(хуков нет)")
        return 0
    for h in items:
        print(_fmt_hook_line(h))
    return 0


def cmd_hook_show(ns: argparse.Namespace) -> int:
    h = hooks_mod.get_hook(ns.hook_id)
    if h is None:
        raise CliError(f"хук {ns.hook_id!r} не найден")
    if _want_json(ns):
        emit(h.to_dict(), as_json=True)
    else:
        d = h.to_dict()
        print(_fmt_hook_line(h))
        print(f"  events_expanded: {', '.join(d['events_expanded'])}")
        print(f"  timeout_sec:     {d['timeout_sec']}")
        print(f"  file:            {hooks_mod.HOOKS_PATH}")
    return 0


def cmd_hook_add(ns: argparse.Namespace) -> int:
    events = list(ns.event or [])
    if not events:
        raise CliError("укажи --event (можно несколько)")
    try:
        hook = hooks_mod.add_hook(
            events=events,
            hook_type=ns.type,
            quest_id=ns.quest,
            name=ns.name or "",
            command=ns.command or "",
            url=ns.url or "",
            path=ns.path or "",
            timeout_sec=float(ns.timeout or 30),
            enabled=not ns.disabled,
        )
    except ValueError as e:
        raise CliError(str(e)) from e
    if _want_json(ns):
        emit(hook.to_dict(), as_json=True)
    else:
        scope = f"quest #{hook.quest_id}" if hook.quest_id is not None else "global"
        print(f"хук {hook.id} добавлен ({scope}, {hook.type})")
        print(_fmt_hook_line(hook))
    return 0


def cmd_hook_remove(ns: argparse.Namespace) -> int:
    removed = hooks_mod.remove_hook(ns.hook_id)
    if removed is None:
        raise CliError(f"хук {ns.hook_id!r} не найден")
    if _want_json(ns):
        emit({"ok": True, "removed": removed.to_dict()}, as_json=True)
    else:
        print(f"удалён хук {removed.id}")
    return 0


def cmd_hook_enable(ns: argparse.Namespace) -> int:
    h = hooks_mod.set_hook_enabled(ns.hook_id, True)
    if h is None:
        raise CliError(f"хук {ns.hook_id!r} не найден")
    if _want_json(ns):
        emit(h.to_dict(), as_json=True)
    else:
        print(f"хук {h.id} включён")
    return 0


def cmd_hook_disable(ns: argparse.Namespace) -> int:
    h = hooks_mod.set_hook_enabled(ns.hook_id, False)
    if h is None:
        raise CliError(f"хук {ns.hook_id!r} не найден")
    if _want_json(ns):
        emit(h.to_dict(), as_json=True)
    else:
        print(f"хук {h.id} выключен")
    return 0


def cmd_hook_events(ns: argparse.Namespace) -> int:
    data = {
        "aliases": {k: list(v) for k, v in sorted(hooks_mod.EVENT_ALIASES.items())},
        "kinds": sorted(hooks_mod.KNOWN_KINDS),
    }
    if _want_json(ns):
        emit(data, as_json=True)
        return 0
    print("aliases:")
    for k, v in sorted(hooks_mod.EVENT_ALIASES.items()):
        print(f"  {k:<18} → {', '.join(v)}")
    print("kinds:")
    for k in sorted(hooks_mod.KNOWN_KINDS):
        print(f"  {k}")
    return 0


# ── argparse ─────────────────────────────────────────────────────────────────


def _add_json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--json",
        action="store_true",
        help="машиночитаемый JSON в stdout",
    )


def _add_api_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--api",
        default=None,
        metavar="URL",
        help=f"база Quests API (иначе QUESTS_API или {API_BASE})",
    )


def build_parser() -> argparse.ArgumentParser:
    json_parent = argparse.ArgumentParser(add_help=False)
    _add_json_flag(json_parent)
    _add_api_flag(json_parent)

    parser = argparse.ArgumentParser(
        prog="quests",
        description=(
            "CLI журнала Quests: квесты через локальный API и хуки "
            "(global / на конкретный квест)."
        ),
        epilog=(
            "Документация: docs/cli.md\n"
            f"API по умолчанию: {API_BASE} (переопредели --api или QUESTS_API)\n"
            f"Хуки: {hooks_mod.HOOKS_PATH} (переопредели QUESTS_HOOKS)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[json_parent],
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="quests 0.1.0",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    # list
    p = sub.add_parser(
        "list",
        help="список квестов",
        aliases=["ls"],
        parents=[json_parent],
    )
    p.add_argument("--status", choices=["active", "delayed", "completed", "failed", "archived"])
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pinned", action="store_true", help="только pinned")
    g.add_argument("--unpinned", action="store_true", help="только не pinned")
    p.add_argument(
        "--category",
        default=None,
        help="фильтр по разделу (id|slug|label|none)",
    )
    p.add_argument(
        "--questline",
        default=None,
        help="фильтр по квестлайну (id|подстрока title|none)",
    )
    p.set_defaults(func=cmd_list)

    # show
    p = sub.add_parser(
        "show",
        help="детали квеста",
        aliases=["get"],
        parents=[json_parent],
    )
    p.add_argument("quest_id", type=int)
    p.set_defaults(func=cmd_show)

    # add
    p = sub.add_parser(
        "add",
        help="создать квест",
        aliases=["create", "new"],
        parents=[json_parent],
    )
    p.add_argument("title")
    p.add_argument("-d", "--description", default="")
    p.add_argument("--pin", action="store_true")
    p.add_argument("--status", default="active")
    p.add_argument(
        "--significance",
        choices=["common", "uncommon", "epic", "legendary"],
        default="common",
    )
    p.add_argument(
        "--step",
        action="append",
        default=[],
        help="шаг (можно повторять); иначе один шаг из title",
    )
    p.add_argument(
        "--category",
        default=None,
        help="раздел: id|slug|label (напр. work)",
    )
    p.add_argument(
        "--questline",
        default=None,
        help="квестлайн: id или подстрока title",
    )
    p.set_defaults(func=cmd_add)

    # llm-add — свободный текст через локальную модель
    p = sub.add_parser(
        "llm-add",
        help="создать квест из свободного текста (Cursor API / опц. Ollama)",
        aliases=["add-llm", "new-llm"],
        parents=[json_parent],
    )
    p.add_argument(
        "text",
        nargs="+",
        help="описание задачи свободным текстом",
    )
    p.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="не спрашивать подтверждение",
    )
    p.add_argument(
        "--variant",
        type=int,
        default=0,
        help="какой вариант из 3 взять (0=самый вероятный)",
    )
    p.set_defaults(func=cmd_llm_add)

    # set (patch fields)
    p = sub.add_parser(
        "set",
        help="изменить поля квеста (раздел, квестлайн, …)",
        parents=[json_parent],
    )
    p.add_argument("quest_id", type=int)
    p.add_argument("--title", default=None)
    p.add_argument("-d", "--description", default=None)
    p.add_argument(
        "--category",
        default=None,
        help="раздел id|slug|label|none",
    )
    p.add_argument(
        "--questline",
        default=None,
        help="квестлайн id|title|none",
    )
    p.add_argument(
        "--significance",
        choices=["common", "uncommon", "epic", "legendary"],
        default=None,
    )
    p.set_defaults(func=cmd_set)

    # pin
    p = sub.add_parser("pin", help="закрепить квест", parents=[json_parent])
    p.add_argument("quest_id", type=int)
    p.add_argument("--off", action="store_true", help="открепить")
    p.set_defaults(func=cmd_pin)

    p = sub.add_parser("unpin", help="открепить квест", parents=[json_parent])
    p.add_argument("quest_id", type=int)
    p.set_defaults(func=cmd_pin, off=True)

    # status / complete / fail
    p = sub.add_parser("status", help="сменить статус", parents=[json_parent])
    p.add_argument("quest_id", type=int)
    p.add_argument("status", choices=["active", "delayed", "completed", "failed", "archived"])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("complete", help="отметить выполненным", parents=[json_parent])
    p.add_argument("quest_id", type=int)
    p.set_defaults(func=cmd_complete)

    p = sub.add_parser("fail", help="провалить квест", parents=[json_parent])
    p.add_argument("quest_id", type=int)
    p.set_defaults(func=cmd_fail)

    # step
    p = sub.add_parser(
        "step",
        help="прогресс шага (+1 по умолчанию)",
        parents=[json_parent],
    )
    p.add_argument("quest_id", type=int)
    p.add_argument("--step-id", type=int, default=None, help="id шага")
    p.add_argument("--title", default=None, help="поиск шага по подстроке title")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--inc", type=int, default=None, help="прибавить N (по умолчанию +1)")
    g.add_argument("--set", type=int, default=None, dest="set", help="установить progress_current")
    g.add_argument("--done", action="store_true", help="довести шаг до total")
    p.set_defaults(func=cmd_step)

    # delete
    p = sub.add_parser(
        "delete",
        help="удалить квест",
        aliases=["rm"],
        parents=[json_parent],
    )
    p.add_argument("quest_id", type=int)
    p.set_defaults(func=cmd_delete)

    # categories
    p = sub.add_parser(
        "categories",
        help="справочник разделов",
        aliases=["cats", "category"],
        parents=[json_parent],
    )
    p.set_defaults(func=cmd_categories)

    # questlines
    qp = sub.add_parser(
        "questline",
        help="квестлайны (цепочки квестов)",
        aliases=["ql", "questlines"],
        parents=[json_parent],
    )
    qsub = qp.add_subparsers(dest="questline_command", metavar="QL_COMMAND", required=True)

    p = qsub.add_parser("list", help="список квестлайнов", aliases=["ls"], parents=[json_parent])
    p.add_argument("--category", default=None, help="фильтр раздела id|slug|label|none")
    p.set_defaults(func=cmd_questline_list)

    p = qsub.add_parser("show", help="детали квестлайна", aliases=["get"], parents=[json_parent])
    p.add_argument("line_id", type=int)
    p.set_defaults(func=cmd_questline_show)

    p = qsub.add_parser("add", help="создать квестлайн", aliases=["create", "new"], parents=[json_parent])
    p.add_argument("title")
    p.add_argument("-d", "--description", default="")
    p.add_argument("--category", default=None, help="раздел id|slug|label")
    p.add_argument("--color", default="#9a9a9a")
    p.add_argument(
        "--icon",
        default="document",
        choices=["document", "flag", "map", "layers", "target", "scroll"],
    )
    p.set_defaults(func=cmd_questline_add)

    p = qsub.add_parser("set", help="изменить квестлайн", parents=[json_parent])
    p.add_argument("line_id", type=int)
    p.add_argument("--title", default=None)
    p.add_argument("-d", "--description", default=None)
    p.add_argument("--category", default=None, help="раздел id|slug|label|none")
    p.add_argument("--color", default=None)
    p.add_argument(
        "--icon",
        default=None,
        choices=["document", "flag", "map", "layers", "target", "scroll"],
    )
    p.set_defaults(func=cmd_questline_set)

    p = qsub.add_parser(
        "delete",
        help="удалить квестлайн (квесты отвяжутся)",
        aliases=["rm"],
        parents=[json_parent],
    )
    p.add_argument("line_id", type=int)
    p.set_defaults(func=cmd_questline_delete)

    # hooks
    hp = sub.add_parser(
        "hook",
        help="управление хуками (global и/или на квест)",
        parents=[json_parent],
    )
    hsub = hp.add_subparsers(dest="hook_command", metavar="HOOK_COMMAND", required=True)

    p = hsub.add_parser(
        "list",
        help="список хуков",
        aliases=["ls"],
        parents=[json_parent],
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--quest", type=int, help="только хуки квеста")
    g.add_argument("--global", dest="global_only", action="store_true", help="только global")
    p.set_defaults(func=cmd_hook_list)

    p = hsub.add_parser("show", help="детали хука", parents=[json_parent])
    p.add_argument("hook_id")
    p.set_defaults(func=cmd_hook_show)

    p = hsub.add_parser("add", help="добавить хук", parents=[json_parent])
    p.add_argument(
        "--event",
        "-e",
        action="append",
        required=True,
        help=(
            "событие или alias: complete|step|status|fail|created|… "
            "или сырой kind (можно повторять)"
        ),
    )
    p.add_argument(
        "--type",
        "-t",
        choices=["script", "webhook", "socket"],
        required=True,
    )
    p.add_argument("--quest", type=int, default=None, help="привязка к квесту; без флага — global")
    p.add_argument("--name", default="", help="человекочитаемое имя")
    p.add_argument("--command", "-c", default="", help="shell для type=script")
    p.add_argument("--url", default="", help="URL для type=webhook (POST JSON)")
    p.add_argument("--path", default="", help="unix-socket path для type=socket")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--disabled", action="store_true", help="создать выключенным")
    p.set_defaults(func=cmd_hook_add)

    p = hsub.add_parser(
        "remove",
        help="удалить хук",
        aliases=["rm", "delete"],
        parents=[json_parent],
    )
    p.add_argument("hook_id")
    p.set_defaults(func=cmd_hook_remove)

    p = hsub.add_parser("enable", help="включить хук", parents=[json_parent])
    p.add_argument("hook_id")
    p.set_defaults(func=cmd_hook_enable)

    p = hsub.add_parser("disable", help="выключить хук", parents=[json_parent])
    p.add_argument("hook_id")
    p.set_defaults(func=cmd_hook_disable)

    p = hsub.add_parser(
        "events",
        help="список alias и kind для --event",
        parents=[json_parent],
    )
    p.set_defaults(func=cmd_hook_events)

    return parser


def main(argv: list[str] | None = None) -> int:
    from quests.envload import load_dotenv_files

    load_dotenv_files()
    parser = build_parser()
    argv_list = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv_list)
    # Root `quests --json <cmd>` and `<cmd> --json` both win.
    if "--json" in argv_list:
        args.json = True

    # Subparser parents can reset --api to None; honor any --api on argv.
    global API_BASE
    api_url = getattr(args, "api", None)
    if not api_url:
        for i, tok in enumerate(argv_list):
            if tok == "--api" and i + 1 < len(argv_list):
                api_url = argv_list[i + 1]
                break
            if tok.startswith("--api="):
                api_url = tok.split("=", 1)[1]
                break
    if api_url:
        API_BASE = str(api_url).rstrip("/")

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    try:
        return int(func(args) or 0)
    except CliError as e:
        return emit_error(str(e), as_json=_want_json(args), code=e.code)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
