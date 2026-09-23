"""Quests MCP (stdio) — journal tools over the HTTP API.

Global Cursor config (``~/.cursor/mcp.json``) so any workspace can use it::

    {
      "mcpServers": {
        "quests": {
          "command": "/home/amarant/.local/bin/uv",
          "args": [
            "run",
            "--directory",
            "/home/amarant/Quests",
            "quests-mcp"
          ],
          "env": {
            "QUESTS_API": "http://SERVER:8765",
            "QUESTS_API_TOKEN": "<from quests-server token add mcp-cursor>"
          }
        }
      }
    }

Local open API: omit ``QUESTS_API_TOKEN`` and point ``QUESTS_API`` at loopback.
Or: ``QUESTS_API=… QUESTS_API_TOKEN=… uv run --directory ~/Quests quests-mcp``.
"""

from __future__ import annotations

import argparse
import base64
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
from quests.refs import resolve_category_id as _shared_resolve_category_id
from quests.refs import resolve_questline_id as _shared_resolve_questline_id

API_BASE = (os.environ.get("QUESTS_API") or f"http://{HOST}:{PORT}").rstrip("/")

ALLOWED_STATUS = {"active", "delayed", "completed", "failed", "archived"}

server = MCPServer(
    "quests",
    instructions=(
        "Quests journal tools. Prefer get_context with a pasted ref like "
        "quest=23 / step=252 / questline=3 / note=12. Use list_questlines then "
        "list_quests to browse missions; list_notes for the knowledge vault. "
        "get_context for full related detail (a quest includes linked_notes "
        "parsed from note= tokens; a note includes refs and backlinks). "
        "Notes are markdown knowledge pages (toolkits, facts) — not quests. "
        "They are not owned by a questline. Link them from a quest/step/"
        "questline description with note=N; notes link back with quest=N / "
        "note=N. Put scripts/config in the note body (fenced code), do not "
        "attach the same zip to every mission. Attachments are binary "
        "artifacts (PDF, images), not toolkits. "
        "To create a new quest use create_quest (title, optional steps inline, "
        "deadline_at + duration_seconds for a reminder window that opens "
        "duration_seconds before deadline_at, automated=true to demote create/start "
        "overlay toasts, category/questline by id or by name — e.g. "
        "category='health', questline='Сайт Рефкул'). "
        "Steps may include check_command, run_mode=poll|once, wait_previous. "
        "To create a new questline (project/theme container) use create_questline. "
        "To create a knowledge page use create_note (title, markdown "
        "description, optional parent_id for the notes tree). "
        "Quest/step/note `description` is markdown in the journal (lists, links, "
        "code, emphasis) — use it; title stays plain. HUD/Telegram show quest "
        "text raw and ignore notes. "
        "To change steps on an existing quest use add_step / update_step / "
        "delete_step (do not replace the whole steps array). "
        "To change quest lifecycle or metadata use update_quest "
        "(status: active|delayed|completed|failed|archived; pin; title; …) — "
        "do not curl the Quests API or dig into the Quests repo for that. "
        "Attachments: get_context and list_quests return metadata only "
        "(filename, size, type, scan_status, comment, available, "
        "source_updated) — never file bytes. Use get_attachment when you "
        "actually need the contents of one file. "
        "If you're blocked on the user's input and they may not be watching this "
        "conversation, use ping_user — it's the only tool guaranteed to interrupt "
        "them via the overlay HUD."
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
    # Bearer token for an instance with accounts enabled; empty when the API is open.
    token = (os.environ.get("QUESTS_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


def _api_raw(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, str]]:
    url = f"{API_BASE}{path}"
    if query:
        q = {k: v for k, v in query.items() if v is not None}
        if q:
            url = f"{url}?{urllib.parse.urlencode(q)}"
    headers = {"Accept": "*/*"}
    token = (os.environ.get("QUESTS_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return raw, hdrs
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


def _attachments_brief(owner_type: str, owner_id: int) -> list[dict[str, Any]]:
    seg = {"questline": "questlines", "note": "notes"}.get(owner_type, "quests")
    try:
        rows = _api_get(f"/api/{seg}/{owner_id}/attachments", {"stat": "0"}) or []
    except RuntimeError:
        # Route missing on an older API, or owner gone — listing quests
        # should still work.
        return []
    out: list[dict[str, Any]] = []
    for a in rows:
        out.append(
            {
                "id": a.get("id"),
                "filename": a.get("filename"),
                "size_bytes": a.get("size_bytes"),
                "content_type": a.get("content_type_detected")
                or a.get("content_type_declared"),
                "scan_status": a.get("scan_status"),
                "comment": a.get("comment"),
                "available": a.get("available"),
                "source_updated": a.get("source_updated"),
            }
        )
    return out


def _tool_query(*, quiet: bool) -> dict[str, str]:
    q = {"source": "mcp"}
    if quiet:
        q["quiet"] = "1"
    return q


def _parse_ref(ref: str) -> tuple[str, int]:
    text = (ref or "").strip()
    for kind in ("questline", "quest", "step", "note"):
        prefix = f"{kind}="
        if text.startswith(prefix):
            return kind, int(text[len(prefix) :].strip())
    raise ValueError(
        f"bad ref {ref!r}; expected quest=N, step=N, questline=N, or note=N"
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


def _resolve_category_id(raw: str | int | None) -> int | None:
    return _shared_resolve_category_id(raw, api_get=_api_get)


def _resolve_questline_id(raw: str | int | None) -> int | None:
    return _shared_resolve_questline_id(raw, api_get=_api_get)


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


def _step_body(s: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": s["title"],
        "description": s.get("description", ""),
        "progress_total": max(1, int(s.get("progress_total", 1))),
        "progress_current": max(0, int(s.get("progress_current", 0))),
    }
    if s.get("sort_order") is not None:
        body["sort_order"] = int(s["sort_order"])
    if s.get("check_command") is not None:
        body["check_command"] = s["check_command"]
    if s.get("check_interval_seconds") is not None:
        body["check_interval_seconds"] = int(s["check_interval_seconds"])
    if s.get("wait_previous") is not None:
        body["wait_previous"] = bool(s["wait_previous"])
    if s.get("run_mode") is not None:
        body["run_mode"] = str(s["run_mode"])
    return body


@server.tool(
    description=(
        "Full related context for a quest, step, questline, or note: "
        "questline (if any), sibling quests, linked_notes (note= tokens), "
        "or the note itself with refs/backlinks/children. Attachment metadata "
        "without file bytes. Pass exactly one of ref / quest / step / questline / note. "
        "ref accepts clipboard form: quest=23 or note=12. Use get_attachment to read a file."
    )
)
def get_context(
    ref: str | None = None,
    quest: int | None = None,
    step: int | None = None,
    questline: int | None = None,
    note: int | None = None,
) -> dict[str, Any]:
    if ref:
        kind, eid = _parse_ref(ref)
        query = {kind: eid}
    else:
        chosen = [
            (k, v)
            for k, v in (
                ("quest", quest),
                ("step", step),
                ("questline", questline),
                ("note", note),
            )
            if v is not None
        ]
        if len(chosen) != 1:
            raise ValueError(
                "provide exactly one of: ref, quest, step, questline, note"
            )
        kind, eid = chosen[0]
        query = {kind: eid}
    return _api_get("/api/context", query)


@server.tool(
    description=(
        "List quests (compact summaries, no step bodies). "
        "Optional filters: status, questline_id, pinned. "
        "Includes attachment metadata (not file bytes) so you can judge "
        "relevance from filename/comment before calling get_attachment."
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
    out = []
    for q in rows:
        row = _quest_summary(q)
        qid = q.get("id")
        if qid is not None:
            row["attachments"] = _attachments_brief("quest", int(qid))
        out.append(row)
    return out


@server.tool(description="List all questlines (id, title, category, color, …).")
def list_questlines() -> list[dict[str, Any]]:
    return _api_get("/api/questlines") or []


@server.tool(
    description=(
        "List quest templates — recurring definitions the scheduler materializes "
        "into quest instances daily/weekly (GET /api/templates). enabled filters "
        "on/off; omit for both."
    )
)
def list_templates(enabled: bool | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if enabled is not None:
        query["enabled"] = "1" if enabled else "0"
    return _api_get("/api/templates", query or None) or []


@server.tool(description="Get one quest template by id, including its steps (GET /api/templates/{id}).")
def get_template(template_id: int) -> dict[str, Any]:
    return _api_get(f"/api/templates/{template_id}")


@server.tool(
    description=(
        "Create a recurring quest template (POST /api/templates). "
        "freq: daily|weekly (weekdays only matters for weekly: comma-separated "
        "0=Mon..6=Sun, default all days). "
        "emit_mode: fixed (materializes unconditionally at the period's first "
        "scheduler tick — deadline_time/duration_seconds only set the resulting "
        "quest's own due time, they do NOT delay creation) or surprise (a cached "
        "per-day chance roll landing at a random moment inside "
        "emit_window_start..emit_window_end). "
        "emit_pool_command is independent of emit_mode and optional: a shell "
        "one-liner, OR — if it starts with a shebang line (#!/usr/bin/env python3 "
        "etc.) — a full inline script. quests writes that text to a temp file and "
        "executes it directly (its own shebang picks the interpreter), so the "
        "script lives in this DB row, not a path on whichever host runs the "
        "scheduler — nothing to hand-deploy. Either way stdout must be a JSON "
        "array of {title, description?, weight?, ref?}; emit_pool_pick items are "
        "drawn weighted-without-replacement each roll and become the created "
        "quest's steps, replacing `steps` below for that roll. ref feeds "
        "anti-repeat (recently-picked items are excluded from the next roll); "
        "omit it and title+description is used as the identity instead. An empty "
        "pool that roll means no quest that period — not an error. A script's own "
        "secrets belong in the *server's* root .env (auto-loaded into its "
        "environment), never hardcoded in the script — unless the user "
        "explicitly asks for hardcoded placeholder/mock values for a one-off "
        "manual test. "
        "category/questline accept an id or a name/substring, resolved the same "
        "way as create_quest's. "
        "steps: same shape as create_quest's `steps` — the template's own "
        "fallback whenever a roll isn't pool-driven (or the pool comes up empty "
        "for surprise mode, though fixed+pool with an empty result skips the "
        "period instead of falling back)."
    )
)
def create_template(
    title: str,
    description: str | None = None,
    freq: str = "daily",
    weekdays: str | None = None,
    timezone: str | None = None,
    emit_mode: str = "fixed",
    emit_chance: float | None = None,
    emit_window_start: str | None = None,
    emit_window_end: str | None = None,
    emit_pool_command: str | None = None,
    emit_pool_pick: int | None = None,
    deadline_time: str | None = None,
    duration_seconds: int | None = None,
    category: str | int | None = None,
    questline: str | int | None = None,
    significance: str | None = None,
    pinned: bool | None = None,
    enabled: bool | None = None,
    automated: bool | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, "freq": freq, "emit_mode": emit_mode}
    if description is not None:
        body["description"] = description
    if weekdays is not None:
        body["weekdays"] = weekdays
    if timezone is not None:
        body["timezone"] = timezone
    if emit_chance is not None:
        body["emit_chance"] = float(emit_chance)
    if emit_window_start is not None:
        body["emit_window_start"] = emit_window_start
    if emit_window_end is not None:
        body["emit_window_end"] = emit_window_end
    if emit_pool_command is not None:
        body["emit_pool_command"] = emit_pool_command
    if emit_pool_pick is not None:
        body["emit_pool_pick"] = int(emit_pool_pick)
    if deadline_time is not None:
        body["deadline_time"] = deadline_time
    if duration_seconds is not None:
        body["duration_seconds"] = int(duration_seconds)
    cat_id = _resolve_category_id(category)
    if cat_id is not None:
        body["category_id"] = cat_id
    line_id = _resolve_questline_id(questline)
    if line_id is not None:
        body["questline_id"] = line_id
    if significance is not None:
        body["significance"] = significance
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if enabled is not None:
        body["enabled"] = bool(enabled)
    if automated is not None:
        body["automated"] = bool(automated)
    if steps is not None:
        body["steps"] = [_step_body(s) for s in steps]
    return _api("POST", "/api/templates", body=body)


@server.tool(
    description=(
        "Update a quest template (PATCH /api/templates/{id}). Only pass fields "
        "to change — same field semantics as create_template. "
        "enabled=true (even re-saving an already-enabled template with some "
        "other field changed) triggers an immediate materialize attempt for the "
        "current period — this is how you fire a fixed-mode or pool template on "
        "demand instead of waiting for the scheduler's own ~15s tick."
    )
)
def update_template(
    template_id: int,
    title: str | None = None,
    description: str | None = None,
    freq: str | None = None,
    weekdays: str | None = None,
    timezone: str | None = None,
    emit_mode: str | None = None,
    emit_chance: float | None = None,
    emit_window_start: str | None = None,
    emit_window_end: str | None = None,
    emit_pool_command: str | None = None,
    emit_pool_pick: int | None = None,
    deadline_time: str | None = None,
    duration_seconds: int | None = None,
    category: str | int | None = None,
    questline: str | int | None = None,
    significance: str | None = None,
    pinned: bool | None = None,
    enabled: bool | None = None,
    automated: bool | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if freq is not None:
        body["freq"] = freq
    if weekdays is not None:
        body["weekdays"] = weekdays
    if timezone is not None:
        body["timezone"] = timezone
    if emit_mode is not None:
        body["emit_mode"] = emit_mode
    if emit_chance is not None:
        body["emit_chance"] = float(emit_chance)
    if emit_window_start is not None:
        body["emit_window_start"] = emit_window_start
    if emit_window_end is not None:
        body["emit_window_end"] = emit_window_end
    if emit_pool_command is not None:
        body["emit_pool_command"] = emit_pool_command
    if emit_pool_pick is not None:
        body["emit_pool_pick"] = int(emit_pool_pick)
    if deadline_time is not None:
        body["deadline_time"] = deadline_time
    if duration_seconds is not None:
        body["duration_seconds"] = int(duration_seconds)
    if category is not None:
        cat_id = _resolve_category_id(category)
        if cat_id is not None:
            body["category_id"] = cat_id
    if questline is not None:
        line_id = _resolve_questline_id(questline)
        if line_id is not None:
            body["questline_id"] = line_id
    if significance is not None:
        body["significance"] = significance
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if enabled is not None:
        body["enabled"] = bool(enabled)
    if automated is not None:
        body["automated"] = bool(automated)
    if steps is not None:
        body["steps"] = [_step_body(s) for s in steps]
    if not body:
        raise ValueError("provide at least one field to update")
    return _api("PATCH", f"/api/templates/{template_id}", body=body)


@server.tool(
    description=(
        "Delete a quest template (DELETE /api/templates/{id}). Does not touch "
        "quests it already materialized."
    )
)
def delete_template(template_id: int) -> dict[str, Any]:
    _api("DELETE", f"/api/templates/{template_id}")
    return {"deleted": template_id}


@server.tool(
    description=(
        "List knowledge notes (markdown pages, not quests). Optional parent_id "
        "filters children of one note; omit for the whole vault. "
        "Link from quests with note=N in the description."
    )
)
def list_notes(parent_id: int | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if parent_id is not None:
        query["parent_id"] = parent_id
    return _api_get("/api/notes", query or None) or []


@server.tool(
    description=(
        "Create a markdown knowledge page (POST /api/notes). Not a quest — no "
        "status, steps, deadline, HUD. parent_id nests it under another note "
        "(vault tree only). Put toolkits (readme/script/config) in description "
        "as markdown/code fences. Cite from quests with note=N."
    )
)
def create_note(
    title: str,
    description: str | None = None,
    parent_id: int | None = None,
    pinned: bool | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title}
    if description is not None:
        body["description"] = description
    if parent_id is not None:
        body["parent_id"] = int(parent_id)
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    return _api("POST", "/api/notes", body=body)


@server.tool(
    description=(
        "Update a note (PATCH /api/notes/{id}). Only pass fields to change. "
        "description is markdown. parent_id=null detaches to the vault root."
    )
)
def update_note(
    note_id: int,
    title: str | None = None,
    description: str | None = None,
    parent_id: int | None = None,
    clear_parent: bool = False,
    pinned: bool | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if clear_parent:
        body["parent_id"] = None
    elif parent_id is not None:
        body["parent_id"] = int(parent_id)
    if pinned is not None:
        body["pinned"] = bool(pinned)
    if sort_order is not None:
        body["sort_order"] = int(sort_order)
    if not body:
        raise ValueError("provide at least one field to update")
    return _api("PATCH", f"/api/notes/{note_id}", body=body)


@server.tool(
    description=(
        "Create a new quest (POST /api/quests). Steps can be passed inline via "
        "`steps`: a list of {title, description?, progress_total?, progress_current?, "
        "sort_order?, check_command?, check_interval_seconds?, wait_previous?, "
        "run_mode?} — if omitted, a single default step named after the quest is "
        "created. run_mode is poll (stdout number) or once (exit 0). wait_previous "
        "gates the auto-step on the previous step. automated=true demotes "
        "created/appeared/started overlay toasts. deadline_at is the moment the quest is due (ISO datetime, UTC — "
        "e.g. '2026-08-20T10:20:00Z'); duration_seconds sizes the urgent/reminder "
        "window that opens that many seconds before deadline_at and triggers the "
        "Telegram/HUD notification (e.g. 7200 for a 2-hour-before reminder). "
        "category and questline accept either a numeric id or a name/substring "
        "(e.g. category='health', questline='Сайт Рефкул') — resolved via "
        "/api/categories and /api/questlines; error if ambiguous. "
        "`description` (and each step's description) is markdown rendered in the "
        "journal — lists, links, inline `code`, emphasis. Title is plain text. "
        "Passing questline "
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
    automated: bool | None = None,
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
    if automated is not None:
        body["automated"] = bool(automated)
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
        body["steps"] = [_step_body(s) for s in steps]
    q = _api("POST", "/api/quests", query=_tool_query(quiet=quiet), body=body)
    return _quest_mutation_result(q)


@server.tool(
    description=(
        "Ping the user when you're blocked on their input and they may have stepped "
        "away from this conversation — creates a quest the normal (never quiet) way, "
        "so it rides the same overlay fullscreen-toast/HUD path a human-created quest "
        "does and is hard to miss. Not for routine progress updates or anything you "
        "can just say in chat — only when you are genuinely stuck without their answer. "
        "message becomes the quest title; details is an optional longer note."
    )
)
def ping_user(
    message: str,
    details: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": message, "pinned": True, "significance": "legendary"}
    if details is not None:
        body["description"] = details
    q = _api("POST", "/api/quests", query=_tool_query(quiet=False), body=body)
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
        "`description` is markdown in the journal (lists, links, code, emphasis). "
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
    check_command: str | None = None,
    check_interval_seconds: int | None = None,
    wait_previous: bool | None = None,
    run_mode: str | None = None,
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
    if check_command is not None:
        body["check_command"] = check_command
    if check_interval_seconds is not None:
        body["check_interval_seconds"] = int(check_interval_seconds)
    if wait_previous is not None:
        body["wait_previous"] = bool(wait_previous)
    if run_mode is not None:
        body["run_mode"] = str(run_mode)
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
        "(e.g. archive when blocked / needs clarification). Also title, description "
        "(markdown in the journal), "
        "pinned, significance, sort_order, deadline_at, duration_seconds, "
        "category_id, questline_id (null to detach), automated. quiet=true skips overlay toasts."
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
    automated: bool | None = None,
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
    if automated is not None:
        body["automated"] = bool(automated)
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
        "Only pass fields to change. `description` is markdown in the journal. "
        "Mark done with progress_current=progress_total "
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
    check_command: str | None = None,
    check_interval_seconds: int | None = None,
    wait_previous: bool | None = None,
    run_mode: str | None = None,
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
    if check_command is not None:
        body["check_command"] = check_command
    if check_interval_seconds is not None:
        body["check_interval_seconds"] = int(check_interval_seconds)
    if wait_previous is not None:
        body["wait_previous"] = bool(wait_previous)
    if run_mode is not None:
        body["run_mode"] = str(run_mode)
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


_GET_ATTACHMENT_MAX = 512 * 1024
_TEXT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
    "+json",
    "+xml",
)


def _looks_text(content_type: str, raw: bytes) -> bool:
    ct = (content_type or "").lower()
    if any(tok in ct for tok in _TEXT_TYPES):
        return True
    sample = raw[:512]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


@server.tool(
    description=(
        "Fetch the contents of one attachment. Metadata is already on "
        "list_quests / get_context — only call this when you decided the file "
        "is relevant. Pass attachment_id plus exactly one of quest / questline / note. "
        "Text is returned as utf-8; anything else as base64. Files over 512 KiB "
        "come back truncated (metadata only plus a note)."
    )
)
def get_attachment(
    attachment_id: int,
    quest: int | None = None,
    questline: int | None = None,
    note: int | None = None,
) -> dict[str, Any]:
    chosen = [
        (k, v)
        for k, v in (("quest", quest), ("questline", questline), ("note", note))
        if v is not None
    ]
    if len(chosen) != 1:
        raise ValueError("provide exactly one of: quest, questline, note")
    kind, owner_id = chosen[0]
    seg = {"quest": "quests", "questline": "questlines", "note": "notes"}[kind]
    meta_rows = _api_get(f"/api/{seg}/{owner_id}/attachments", {"stat": "0"}) or []
    meta = next((a for a in meta_rows if a.get("id") == attachment_id), None)
    raw, _hdrs = _api_raw(
        "GET", f"/api/{seg}/{owner_id}/attachments/{attachment_id}"
    )
    out: dict[str, Any] = {
        "id": attachment_id,
        "owner_type": kind,
        "owner_id": owner_id,
        "filename": (meta or {}).get("filename"),
        "size_bytes": (meta or {}).get("size_bytes", len(raw)),
        "content_type": (meta or {}).get("content_type_detected")
        or (meta or {}).get("content_type_declared"),
        "comment": (meta or {}).get("comment"),
        "truncated": False,
    }
    if len(raw) > _GET_ATTACHMENT_MAX:
        out["truncated"] = True
        out["note"] = (
            f"file is {len(raw)} bytes; contents omitted above "
            f"{_GET_ATTACHMENT_MAX} bytes"
        )
        return out
    if _looks_text(str(out.get("content_type") or ""), raw):
        out["text"] = raw.decode("utf-8", errors="replace")
        out["encoding"] = "utf-8"
    else:
        out["base64"] = base64.standard_b64encode(raw).decode("ascii")
        out["encoding"] = "base64"
    return out


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
