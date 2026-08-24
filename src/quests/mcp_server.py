"""Quests MCP (stdio) — journal tools over the HTTP API.

Global Cursor config (``~/.cursor/mcp.json``) so any workspace can use it::

    {
      "mcpServers": {
        "quests": {
          "command": "/usr/bin/uv",
          "args": [
            "run",
            "--directory",
            "/home/amarant/Documents/projects/Quests",
            "quests-mcp"
          ],
          "env": { "QUESTS_API": "http://127.0.0.1:8765" }
        }
      }
    }

Or: ``QUESTS_API=… uv run quests-mcp --api http://…``
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

from mcp.server.mcpserver import MCPServer

from quests.config import HOST, PORT
from quests.envload import load_dotenv_files

API_BASE = (os.environ.get("QUESTS_API") or f"http://{HOST}:{PORT}").rstrip("/")

ALLOWED_STATUS = {"active", "delayed", "completed", "failed", "archived"}

server = MCPServer(
    "quests",
    instructions=(
        "Quests journal tools. Prefer get_context with a pasted ref like "
        "quest=23 / step=252 / questline=3. Use list_questlines then list_quests "
        "to browse; get_context for full related detail. "
        "To create a new quest use create_quest (title, optional steps inline, "
        "deadline_at + duration_seconds for a reminder window that opens "
        "duration_seconds before deadline_at, category/questline by id or by "
        "name — e.g. category='health', questline='Сайт Рефкул'). "
        "To create a new questline (project/theme container) use create_questline. "
        "To change steps on an existing quest use add_step / update_step / "
        "delete_step (do not replace the whole steps array). "
        "To change quest lifecycle or metadata use update_quest "
        "(status: active|delayed|completed|failed|archived; pin; title; …) — "
        "do not curl the Quests API or dig into the Quests repo for that."
    ),
)


def _api(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
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
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = parsed.get("detail", detail)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"API {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"cannot reach Quests API ({API_BASE}): {e.reason}"
        ) from e


def _api_get(path: str, query: dict[str, Any] | None = None) -> Any:
    return _api("GET", path, query=query)


def _tool_query(*, quiet: bool) -> dict[str, str]:
    q = {"source": "mcp"}
    if quiet:
        q["quiet"] = "1"
    return q


def _parse_ref(ref: str) -> tuple[str, int]:
    text = (ref or "").strip()
    for kind in ("questline", "quest", "step"):
        prefix = f"{kind}="
        if text.startswith(prefix):
            return kind, int(text[len(prefix) :].strip())
    raise ValueError(
        f"bad ref {ref!r}; expected quest=N, step=N, or questline=N"
    )


def _quest_summary(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": q.get("id"),
        "title": q.get("title"),
        "status": q.get("status"),
        "significance": q.get("significance"),
        "pinned": q.get("pinned"),
        "progress_label": q.get("progress_label"),
        "steps_done": q.get("steps_done"),
        "steps_total": q.get("steps_total"),
        "category_id": q.get("category_id"),
        "category_slug": q.get("category_slug"),
        "category_label": q.get("category_label"),
        "questline_id": q.get("questline_id"),
        "questline_title": q.get("questline_title"),
        "deadline_at": q.get("deadline_at"),
        "updated_at": q.get("updated_at"),
    }


def _steps_brief(q: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for s in q.get("steps") or []:
        row = {
            "id": s.get("id"),
            "title": s.get("title"),
            "progress_current": s.get("progress_current"),
            "progress_total": s.get("progress_total"),
            "done": s.get("done"),
            "sort_order": s.get("sort_order"),
        }
        desc = s.get("description")
        if desc:
            row["description"] = desc
        out.append(row)
    return out


def _is_none_token(raw: str) -> bool:
    return raw.strip().lower() in {"", "none", "-", "нет", "null"}


def _resolve_ref_id(raw: str | int | None, *, path: str, needle_fields: tuple[str, ...]) -> int | None:
    """Resolve a category/questline given as id, or as a name/substring (case-insensitive),
    the same way the CLI's ResolveCategoryID/ResolveQuestlineID do."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if _is_none_token(raw):
        return None
    text = raw.strip()
    if text.lstrip("-").isdigit():
        return int(text)
    needle = text.lower()
    rows = _api_get(path) or []
    matches = [
        row["id"]
        for row in rows
        if any(needle == str(row.get(f, "")).lower() or needle in str(row.get(f, "")).lower() for f in needle_fields)
    ]
    exact = [row["id"] for row in rows if any(str(row.get(f, "")).lower() == needle for f in needle_fields)]
    if exact:
        matches = exact
    if not matches:
        raise ValueError(f"{path.rsplit('/', 1)[-1]} {raw!r} not found")
    if len(matches) > 1:
        raise ValueError(f"multiple matches for {raw!r} in {path}; pass a numeric id")
    return matches[0]


def _resolve_category_id(raw: str | int | None) -> int | None:
    return _resolve_ref_id(raw, path="/api/categories", needle_fields=("slug", "label"))


def _resolve_questline_id(raw: str | int | None) -> int | None:
    return _resolve_ref_id(raw, path="/api/questlines", needle_fields=("title",))


def _quest_mutation_result(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": q.get("id"),
        "title": q.get("title"),
        "status": q.get("status"),
        "pinned": q.get("pinned"),
        "significance": q.get("significance"),
        "progress_label": q.get("progress_label"),
        "questline_id": q.get("questline_id"),
        "category_id": q.get("category_id"),
        "steps": _steps_brief(q),
    }


@server.tool(
    description=(
        "Full related context for a quest, step, or questline: questline (if any), "
        "sibling quests on that line, and all steps/progress. Pass exactly one of "
        "ref / quest / step / questline. ref accepts clipboard form: quest=23."
    )
)
def get_context(
    ref: str | None = None,
    quest: int | None = None,
    step: int | None = None,
    questline: int | None = None,
) -> dict[str, Any]:
    if ref:
        kind, eid = _parse_ref(ref)
        query = {kind: eid}
    else:
        chosen = [
            (k, v)
            for k, v in (("quest", quest), ("step", step), ("questline", questline))
            if v is not None
        ]
        if len(chosen) != 1:
            raise ValueError(
                "provide exactly one of: ref, quest, step, questline"
            )
        kind, eid = chosen[0]
        query = {kind: eid}
    return _api_get("/api/context", query)


@server.tool(
    description=(
        "List quests (compact summaries, no step bodies). "
        "Optional filters: status, questline_id, pinned."
    )
)
def list_quests(
    status: str | None = None,
    questline_id: int | None = None,
    pinned: bool | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    if pinned is not None:
        query["pinned"] = str(pinned).lower()
    rows = _api_get("/api/quests", query) or []
    if questline_id is not None:
        rows = [q for q in rows if q.get("questline_id") == questline_id]
    return [_quest_summary(q) for q in rows]


@server.tool(description="List all questlines (id, title, category, color, …).")
def list_questlines() -> list[dict[str, Any]]:
    return _api_get("/api/questlines") or []


@server.tool(
    description=(
        "Create a new quest (POST /api/quests). Steps can be passed inline via "
        "`steps`: a list of {title, description?, progress_total?, progress_current?, "
        "sort_order?} — if omitted, a single default step named after the quest is "
        "created. deadline_at is the moment the quest is due (ISO datetime, UTC — "
        "e.g. '2026-08-20T10:20:00Z'); duration_seconds sizes the urgent/reminder "
        "window that opens that many seconds before deadline_at and triggers the "
        "Telegram/HUD notification (e.g. 7200 for a 2-hour-before reminder). "
        "category and questline accept either a numeric id or a name/substring "
        "(e.g. category='health', questline='Сайт Рефкул') — resolved via "
        "/api/categories and /api/questlines; error if ambiguous. Passing questline "
        "makes the quest inherit that questline's category. quiet=true skips overlay toasts."
    )
)
def create_quest(
    title: str,
    description: str | None = None,
    status: str | None = None,
    significance: str | None = None,
    pinned: bool | None = None,
    sort_order: int | None = None,
    deadline_at: str | None = None,
    duration_seconds: int | None = None,
    category: str | None = None,
    questline: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    quiet: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title}
    if description is not None:
        body["description"] = description
    if status is not None:
        st = str(status).strip().lower()
        if st not in ALLOWED_STATUS:
            raise ValueError(f"bad status {status!r}; expected one of {sorted(ALLOWED_STATUS)}")
        body["status"] = st
    if significance is not None:
        body["significance"] = significance
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    if deadline_at is not None:
        body["deadline_at"] = deadline_at
    if duration_seconds is not None:
        body["duration_seconds"] = int(duration_seconds)
    questline_id = _resolve_questline_id(questline)
    if questline_id is not None:
        body["questline_id"] = questline_id
    else:
        cat_id = _resolve_category_id(category)
        if cat_id is not None:
            body["category_id"] = cat_id
    if steps:
        body["steps"] = [
            {
                "title": s["title"],
                "description": s.get("description", ""),
                "progress_total": max(1, int(s.get("progress_total", 1))),
                "progress_current": max(0, int(s.get("progress_current", 0))),
                **({"sort_order": int(s["sort_order"])} if s.get("sort_order") is not None else {}),
            }
            for s in steps
        ]
    q = _api("POST", "/api/quests", query=_tool_query(quiet=quiet), body=body)
    return _quest_mutation_result(q)


@server.tool(
    description=(
        "Create a new questline (POST /api/questlines) — a themed project/series "
        "that quests can be attached to via update_quest(questline_id=...) or "
        "create_quest(questline=...). category accepts id or name/substring."
    )
)
def create_questline(
    title: str,
    description: str | None = None,
    category: str | None = None,
    color: str | None = None,
    icon: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title}
    if description is not None:
        body["description"] = description
    if color is not None:
        body["color"] = color
    if icon is not None:
        body["icon"] = icon
    cat_id = _resolve_category_id(category)
    if cat_id is not None:
        body["category_id"] = cat_id
    return _api("POST", "/api/questlines", body=body)


@server.tool(
    description=(
        "Add one step to an existing quest (POST /api/quests/{id}/steps). "
        "Returns quest id, progress_label, and steps brief. quiet=true skips overlay toasts."
    )
)
def add_step(
    quest_id: int,
    title: str,
    description: str | None = None,
    progress_total: int = 1,
    progress_current: int = 0,
    sort_order: int | None = None,
    quiet: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "progress_total": max(1, int(progress_total)),
        "progress_current": max(0, int(progress_current)),
    }
    if description is not None:
        body["description"] = description
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    q = _api(
        "POST",
        f"/api/quests/{quest_id}/steps",
        query=_tool_query(quiet=quiet),
        body=body,
    )
    return _quest_mutation_result(q)


@server.tool(
    description=(
        "Update quest fields (PATCH /api/quests/{id}). Only pass fields to change. "
        "Use for lifecycle: status=active|delayed|completed|failed|archived "
        "(e.g. archive when blocked / needs clarification). Also title, description, "
        "pinned, significance, sort_order, deadline_at, duration_seconds, "
        "category_id, questline_id (null to detach). quiet=true skips overlay toasts."
    )
)
def update_quest(
    quest_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    significance: str | None = None,
    pinned: bool | None = None,
    sort_order: int | None = None,
    deadline_at: str | None = None,
    duration_seconds: int | None = None,
    category_id: int | None = None,
    questline_id: int | None = None,
    clear_questline: bool = False,
    quiet: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if status is not None:
        st = str(status).strip().lower()
        if st not in ALLOWED_STATUS:
            raise ValueError(
                f"bad status {status!r}; expected one of {sorted(ALLOWED_STATUS)}"
            )
        body["status"] = st
    if significance is not None:
        body["significance"] = significance
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    if deadline_at is not None:
        body["deadline_at"] = deadline_at
    if duration_seconds is not None:
        body["duration_seconds"] = int(duration_seconds)
    if category_id is not None:
        body["category_id"] = int(category_id)
    if clear_questline:
        body["questline_id"] = None
    elif questline_id is not None:
        body["questline_id"] = int(questline_id)
    if not body:
        raise ValueError("provide at least one field to update")
    q = _api(
        "PATCH",
        f"/api/quests/{quest_id}",
        query=_tool_query(quiet=quiet),
        body=body,
    )
    return _quest_mutation_result(q)


@server.tool(
    description=(
        "Update fields on one step (PATCH /api/quests/{id}/steps/{step_id}). "
        "Only pass fields to change. Mark done with progress_current=progress_total "
        "(or progress_current equal to existing total). quiet=true skips overlay toasts."
    )
)
def update_step(
    quest_id: int,
    step_id: int,
    title: str | None = None,
    description: str | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    sort_order: int | None = None,
    quiet: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if progress_current is not None:
        body["progress_current"] = int(progress_current)
    if progress_total is not None:
        body["progress_total"] = max(1, int(progress_total))
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    if not body:
        raise ValueError("provide at least one field to update")
    q = _api(
        "PATCH",
        f"/api/quests/{quest_id}/steps/{step_id}",
        query=_tool_query(quiet=quiet),
        body=body,
    )
    return _quest_mutation_result(q)


@server.tool(
    description=(
        "Delete one step (DELETE /api/quests/{id}/steps/{step_id}). "
        "Fails if it is the last step. quiet=true skips overlay toasts."
    )
)
def delete_step(
    quest_id: int,
    step_id: int,
    quiet: bool = True,
) -> dict[str, Any]:
    q = _api(
        "DELETE",
        f"/api/quests/{quest_id}/steps/{step_id}",
        query=_tool_query(quiet=quiet),
    )
    return _quest_mutation_result(q)


def main(argv: list[str] | None = None) -> None:
    global API_BASE
    load_dotenv_files()
    parser = argparse.ArgumentParser(prog="quests-mcp", description="Quests MCP server")
    parser.add_argument(
        "--api",
        default=None,
        metavar="URL",
        help=f"Quests API base (else QUESTS_API or {API_BASE})",
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.api:
        API_BASE = str(args.api).rstrip("/")
    elif os.environ.get("QUESTS_API"):
        API_BASE = os.environ["QUESTS_API"].rstrip("/")

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
