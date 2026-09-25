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
import mimetypes
import os
import subprocess
import sys
import tempfile
import uuid
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
        "Quests journal tools. Use list_questlines then list_quests to browse "
        "missions; list_notes for the knowledge vault. get_base_context for one "
        "entity's own fields (quest/step/questline — accepts a pasted ref like "
        "quest=23 / step=252 / questline=3); get_note_context for a note's own "
        "fields plus refs/backlinks/children (note=12). get_active_context for "
        "live/pending work; get_inactive_context for completed/failed/archived "
        "history with full steps — together they cover every quest, full detail. "
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
        "Attachments: list_quests and the get_*_context tools return metadata only "
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


def _api_upload_file(path: str, file_path: str, *, field: str = "file") -> Any:
    """POST a local file as multipart/form-data (icon uploads etc.)."""
    try:
        with open(file_path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise ValueError(f"cannot read {file_path}: {e}") from e
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + raw + f"\r\n--{boundary}--\r\n".encode("utf-8")
    url = f"{API_BASE}{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    token = (os.environ.get("QUESTS_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_resp = resp.read()
            return json.loads(raw_resp.decode("utf-8")) if raw_resp else None
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
        "Full context for one note: its own description plus refs (quest=N/"
        "note=N tokens it cites) and backlinks (other quests/notes that cite "
        "it) and children (nested notes). This is the only tool that resolves "
        "note refs/backlinks — quests/steps/questlines don't need it, use "
        "get_base_context or get_active_context/get_inactive_context for those."
    )
)
def get_note_context(note_id: int) -> dict[str, Any]:
    return _api_get("/api/context", {"note": note_id})


@server.tool(
    description=(
        "The object's own direct fields, no siblings/linked_notes bloat. "
        "For a questline: description, attachments, and its quests (id/title/"
        "status/significance/category/...) across every status. For a quest: "
        "description, steps, attachments, and a brief questline (if any). For "
        "a step: its description/progress and a brief owning quest. Pass "
        "exactly one of ref / quest / step / questline (notes aren't "
        "supported here — use get_note_context for those)."
    )
)
def get_base_context(
    ref: str | None = None,
    quest: int | None = None,
    step: int | None = None,
    questline: int | None = None,
) -> dict[str, Any]:
    if ref:
        kind, eid = _parse_ref(ref)
        if kind == "note":
            raise ValueError("get_base_context does not support notes; use get_note_context")
    else:
        chosen = [
            (k, v)
            for k, v in (("quest", quest), ("step", step), ("questline", questline))
            if v is not None
        ]
        if len(chosen) != 1:
            raise ValueError("provide exactly one of: ref, quest, step, questline")
        kind, eid = chosen[0]

    if kind == "questline":
        resp = _api_get("/api/context", {"questline": eid})
        line = resp.get("questline") or {}
        return {
            "id": line.get("id"),
            "title": line.get("title"),
            "description": line.get("description"),
            "color": line.get("color"),
            "icon": line.get("icon"),
            "icon_url": line.get("icon_url"),
            "category_id": line.get("category_id"),
            "category_slug": line.get("category_slug"),
            "category_label": line.get("category_label"),
            "attachments": (resp.get("attachments") or {}).get("questline", []),
            "quests": [_quest_summary(q) for q in resp.get("quests") or []],
        }

    if kind == "quest":
        resp = _api_get("/api/context", {"quest": eid})
        q = next((r for r in resp.get("quests") or [] if r.get("id") == eid), None)
        if q is None:
            raise ValueError(f"quest={eid} not found")
        line = resp.get("questline")
        out: dict[str, Any] = {
            "id": q.get("id"),
            "title": q.get("title"),
            "description": q.get("description"),
            "status": q.get("status"),
            "significance": q.get("significance"),
            "pinned": q.get("pinned"),
            "category_id": q.get("category_id"),
            "category_slug": q.get("category_slug"),
            "category_label": q.get("category_label"),
            "deadline_at": q.get("deadline_at"),
            "created_at": q.get("created_at"),
            "updated_at": q.get("updated_at"),
            "steps": _steps_brief(q),
            "attachments": ((resp.get("attachments") or {}).get("by_quest") or {}).get(
                str(eid), []
            ),
            "questline": None,
        }
        if line:
            out["questline"] = {
                "id": line.get("id"),
                "title": line.get("title"),
                "color": line.get("color"),
                "icon": line.get("icon"),
                "category_id": line.get("category_id"),
                "category_label": line.get("category_label"),
            }
        return out

    # step
    resp = _api_get("/api/context", {"step": eid})
    owner = None
    step_row = None
    for q in resp.get("quests") or []:
        for s in q.get("steps") or []:
            if s.get("id") == eid:
                owner, step_row = q, s
                break
        if owner:
            break
    if owner is None:
        raise ValueError(f"step={eid} not found")
    return {
        "step": {
            "id": step_row.get("id"),
            "title": step_row.get("title"),
            "description": step_row.get("description"),
            "progress_current": step_row.get("progress_current"),
            "progress_total": step_row.get("progress_total"),
            "done": step_row.get("done"),
            "sort_order": step_row.get("sort_order"),
        },
        "quest": _quest_summary(owner),
    }


def _quests_by_status_context(
    statuses: tuple[str, ...],
    questline: str | int | None,
    *,
    all_steps: bool,
) -> dict[str, Any]:
    qline_id = _resolve_questline_id(questline) if questline is not None else None
    rows: list[dict[str, Any]] = []
    for st in statuses:
        rows.extend(_api_get("/api/quests", {"status": st}) or [])
    if qline_id is not None:
        rows = [q for q in rows if q.get("questline_id") == qline_id]

    quests_out = []
    for row in rows:
        qid = row.get("id")
        if qid is None:
            continue
        resp = _api_get("/api/context", {"quest": qid})
        q = next((r for r in resp.get("quests") or [] if r.get("id") == qid), None)
        if q is None:
            continue
        steps = [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "description": s.get("description"),
                "progress_current": s.get("progress_current"),
                "progress_total": s.get("progress_total"),
                **({"done": s.get("done")} if all_steps else {}),
            }
            for s in q.get("steps") or []
            if all_steps or not s.get("done")
        ]
        quests_out.append(
            {
                "id": q.get("id"),
                "title": q.get("title"),
                "description": q.get("description"),
                "status": q.get("status"),
                "significance": q.get("significance"),
                "pinned": q.get("pinned"),
                "deadline_at": q.get("deadline_at"),
                "questline_id": q.get("questline_id"),
                "questline_title": q.get("questline_title"),
                "steps": steps,
                "attachments": _attachments_brief("quest", int(qid)),
            }
        )
    return {"quests": quests_out, "count": len(quests_out)}


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


@server.tool(
    description=(
        "Only the live work: quests with status active/delayed, each with just "
        "its undone steps (done ones dropped). No completed/failed/archived "
        "quests, no finished steps — use this instead of list_quests when you "
        "just need 'what's actually pending', without wading through history. "
        "Optional questline filter (id or name, e.g. questline='Сайт Рефкул'); "
        "omit for everything pending across all questlines. Complements "
        "get_inactive_context — together they cover every quest, every step."
    )
)
def get_active_context(questline: str | int | None = None) -> dict[str, Any]:
    return _quests_by_status_context(("active", "delayed"), questline, all_steps=False)


@server.tool(
    description=(
        "The history: quests with status completed/failed/archived, each with "
        "all of its steps (done and not, each flagged `done`) — the complement "
        "of get_active_context. Use it for 'what did we already do' or 'what's "
        "in this questline besides the live stuff', instead of list_quests when "
        "you also want step bodies. Optional questline filter (id or name). "
        "get_active_context ∪ get_inactive_context ≈ every quest in scope, full "
        "steps — the same ground get_context used to cover before it was split "
        "into these two status-scoped tools plus get_note_context for notes."
    )
)
def get_inactive_context(questline: str | int | None = None) -> dict[str, Any]:
    return _quests_by_status_context(
        ("completed", "failed", "archived"), questline, all_steps=True
    )


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
        "quest's steps, replacing `steps` below for that roll. emit_pool_pick<=0 "
        "means take everything new instead of N random ones: no weighted "
        "sampling, just whatever's left after the anti-repeat filter below — use "
        "this for a pool that must not silently drop items (e.g. unread mail), "
        "since a weighted N-of-M sample would. ref feeds anti-repeat "
        "(recently-picked items are excluded from the next roll); omit it and "
        "title+description is used as the identity instead. An empty pool that "
        "roll means no quest that period — not an error. If the command/script "
        "fails 3 rolls running (bad creds, network, non-zero exit, invalid "
        "JSON — nothing about this is logged anywhere else), the *next* "
        "materialize still creates a quest: status=failed, description holds the "
        "last attempt's stderr/parse-error trace, so the failure is visible in "
        "the journal instead of only queryable in templateemitroll. A script's own "
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


# Mirrors go/internal/schedule/materialize.go: emitPoolTimeout (20s) and the
# shebang-body-vs-sh-one-liner dispatch of execEmitPoolCommand. Kept in sync by
# hand — this is a dry-run, not the scheduler's own execution path.
_EMIT_POOL_TIMEOUT_SECONDS = 20
_EMIT_POOL_MAX_ATTEMPTS = 3


def _run_emit_pool_command(command: str) -> dict[str, Any]:
    """Execute an emit_pool_command exactly as the Go scheduler would and parse
    its stdout. Returns a structured trace instead of raising — a failing script
    is the normal thing you're debugging here.
    """
    stripped = command.lstrip(" \t\r\n")
    home = os.path.expanduser("~")
    env = os.environ  # main() already loaded ROOT/.env, same source the server uses
    script_path: str | None = None
    try:
        if stripped.startswith("#!"):
            exec_mode = "script"  # shebang body → temp file, its own interpreter
            fd, script_path = tempfile.mkstemp(prefix="quests-emit-pool-")
            with os.fdopen(fd, "w") as fh:
                fh.write(command)
            os.chmod(script_path, 0o700)
            argv = [script_path]
        else:
            exec_mode = "sh -c"
            argv = ["sh", "-c", command]
        try:
            proc = subprocess.run(
                argv,
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                timeout=_EMIT_POOL_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as e:
            return {
                "ok": False,
                "exec_mode": exec_mode,
                "error": f"timed out after {_EMIT_POOL_TIMEOUT_SECONDS}s",
                "stdout": _clip(e.stdout or ""),
                "stderr": _clip(e.stderr or ""),
            }
    finally:
        if script_path:
            try:
                os.remove(script_path)
            except OSError:
                pass

    trace = {
        "exec_mode": exec_mode,
        "exit_code": proc.returncode,
        "stdout": _clip(proc.stdout),
        "stderr": _clip(proc.stderr),
    }
    if proc.returncode != 0:
        # Same as the scheduler: a non-zero exit is a failure regardless of
        # stdout — after _EMIT_POOL_MAX_ATTEMPTS it materializes a failed quest.
        trace["ok"] = False
        trace["error"] = f"non-zero exit ({proc.returncode})"
        return trace
    try:
        raw = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError as e:
        trace["ok"] = False
        trace["error"] = f"invalid JSON on stdout: {e}"
        return trace
    if not isinstance(raw, list):
        trace["ok"] = False
        trace["error"] = "stdout JSON must be an array of pool items"
        return trace

    items: list[dict[str, Any]] = []
    dropped_empty_title = 0
    for entry in raw:
        if not isinstance(entry, dict):
            trace["ok"] = False
            trace["error"] = "each pool item must be a JSON object {title, description?, weight?, ref?}"
            return trace
        title = str(entry.get("title") or "").strip()
        if not title:
            dropped_empty_title += 1  # scheduler silently drops empty-title items
            continue
        weight = entry.get("weight")
        eff = 1.0 if weight is None else (float(weight) if float(weight) >= 0 else 0.0)
        ref = str(entry.get("ref") or "").strip()
        items.append(
            {
                "title": title,
                "description": entry.get("description") or "",
                "weight": weight,
                "effective_weight": eff,
                "ref": ref or None,
                "dedup_key": ref or f"{title}\x00{entry.get('description') or ''}",
            }
        )

    positive = [it for it in items if it["effective_weight"] > 0]
    trace["ok"] = True
    trace["items"] = items
    trace["kept_count"] = len(items)
    trace["dropped_empty_title"] = dropped_empty_title
    trace["positive_count"] = len(positive)
    if len(positive) < len(items):
        trace["zero_weight_count"] = len(items) - len(positive)
    return trace


def _clip(s: str, n: int = 4000) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


@server.tool(
    description=(
        "Dry-run an emit_pool_command and show the pool it would produce — the "
        "missing half of authoring a pool template through MCP (create_template/"
        "update_template can already store the command). Runs it exactly as the "
        "scheduler does: a value starting with '#!' is written to a temp file "
        "and executed by its own shebang, anything else runs via `sh -c`; cwd is "
        "$HOME, env is the server process env (root .env already loaded), 20s "
        "timeout. Pass either `command` (the script/one-liner text you're "
        "drafting) or `template_id` (dry-run its stored emit_pool_command). "
        "Returns ok plus the parsed items (title/description/weight/"
        "effective_weight/ref/dedup_key), how many empty-title items were "
        "dropped and how many have zero weight, or on failure the exit code and "
        "stdout/stderr trace — the same signal the scheduler would act on. Does "
        "NOT persist a roll, apply the anti-repeat filter across periods, or "
        "materialize a quest; it just shows what the command emits right now. "
        "Note pick semantics for context: emit_pool_pick<=0 takes every new "
        "item, >0 weighted-samples that many (excluding recently picked refs). "
        "CAUTION, two ways a green result here can still mislead: (1) this "
        "tool runs the command for real on whatever host the MCP server "
        "itself is on — not inside the API server's own environment (its "
        "own container/host, its own env file). A command that shells out to "
        "host-only tools, or reads env vars only the API server's env file "
        "sets, can pass here and still fail for real — confirmed twice: once "
        "against pacman/checkupdates/vercmp missing in the API container, "
        "once against a script needing env vars present in the MCP host's "
        ".env but absent from the API container's own env file. (2) it does "
        "NOT sandbox the command — any side effect the command performs for "
        "real (network writes, marking something read/consumed upstream, "
        "local files) happens for real, exactly as if the scheduler ran it; "
        "only Quests' own bookkeeping (the roll row, the quest) is skipped. "
        "For a script with real side effects, dry-run it against a copy with "
        "a throwaway target (a test marker path, a sandbox account, etc.) "
        "instead of the one it'll actually use."
    )
)
def dry_run_emit_pool(
    command: str | None = None,
    template_id: int | None = None,
) -> dict[str, Any]:
    chosen = [v for v in (command, template_id) if v is not None]
    if len(chosen) != 1:
        raise ValueError("provide exactly one of: command, template_id")
    if template_id is not None:
        tmpl = _api_get(f"/api/templates/{template_id}")
        cmd = (tmpl or {}).get("emit_pool_command")
        if not cmd or not str(cmd).strip():
            raise ValueError(f"template {template_id} has no emit_pool_command set")
        source: dict[str, Any] = {
            "source": f"template={template_id}",
            "emit_pool_pick": (tmpl or {}).get("emit_pool_pick"),
        }
        cmd = str(cmd)
    else:
        cmd = command
        source = {"source": "inline"}
    result = _run_emit_pool_command(cmd)
    return {**source, **result}


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
        "Permanently delete a note (DELETE /api/notes/{id}). Also drops its "
        "refs/backlinks. Children are not cascaded — detach or re-parent them "
        "first, or the API will reject the delete if it enforces that."
    )
)
def delete_note(note_id: int) -> dict[str, Any]:
    _api("DELETE", f"/api/notes/{note_id}")
    return {"deleted": note_id}


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
        "Update a questline (PATCH /api/questlines/{id}). Only pass fields to "
        "change. description is markdown. category accepts an id or a "
        "name/substring. icon is the string code (e.g. 'target'), not a custom "
        "uploaded image — see set_icon for that."
    )
)
def update_questline(
    questline_id: int,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    color: str | None = None,
    icon: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if color is not None:
        body["color"] = color
    if icon is not None:
        body["icon"] = icon
    cat_id = _resolve_category_id(category)
    if cat_id is not None:
        body["category_id"] = cat_id
    if not body:
        raise ValueError("provide at least one field to update")
    return _api("PATCH", f"/api/questlines/{questline_id}", body=body)


@server.tool(
    description=(
        "Permanently delete a questline (DELETE /api/questlines/{id}). Quests "
        "that belonged to it are not deleted — detach them first with "
        "update_quest(clear_questline=True) if you want them to survive as "
        "standalone quests, or the API will reject/cascade per its own rules."
    )
)
def delete_questline(questline_id: int) -> dict[str, Any]:
    _api("DELETE", f"/api/questlines/{questline_id}")
    return {"deleted": questline_id}


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
        "list_quests / the get_*_context tools — only call this when you decided the file "
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


@server.tool(
    description=(
        "Upload a custom icon image (POST /api/{questlines|notes}/{id}/icon) "
        "for a questline or note, replacing its string icon code with an "
        "uploaded picture. Pass exactly one of questline / note plus a local "
        "file_path (png/jpg, max 512 KiB). This reads the file from the local "
        "filesystem where the MCP server runs, not from the conversation."
    )
)
def set_icon(
    file_path: str,
    questline: int | None = None,
    note: int | None = None,
) -> dict[str, Any]:
    chosen = [(k, v) for k, v in (("questline", questline), ("note", note)) if v is not None]
    if len(chosen) != 1:
        raise ValueError("provide exactly one of: questline, note")
    kind, owner_id = chosen[0]
    seg = {"questline": "questlines", "note": "notes"}[kind]
    return _api_upload_file(f"/api/{seg}/{owner_id}/icon", file_path)


@server.tool(
    description=(
        "Remove a questline's or note's uploaded custom icon (DELETE "
        "/api/{questlines|notes}/{id}/icon), reverting to its plain string "
        "icon code. Pass exactly one of questline / note."
    )
)
def delete_icon(
    questline: int | None = None,
    note: int | None = None,
) -> dict[str, Any]:
    chosen = [(k, v) for k, v in (("questline", questline), ("note", note)) if v is not None]
    if len(chosen) != 1:
        raise ValueError("provide exactly one of: questline, note")
    kind, owner_id = chosen[0]
    seg = {"questline": "questlines", "note": "notes"}[kind]
    _api("DELETE", f"/api/{seg}/{owner_id}/icon")
    return {"cleared_icon": {kind: owner_id}}


@server.tool(
    description=(
        "Set the accent/line color of a questline or note (PATCH `color` on "
        "/api/{questlines|notes}/{id}) — the swatch shown behind its icon in "
        "the tree/HUD. Pass a hex string (e.g. '#c47a20'; a leading '#' is "
        "added if missing) plus exactly one of questline / note. This is the "
        "string `color` field, separate from an uploaded custom icon image "
        "(see set_icon). For a questline it's the same field "
        "update_questline(color=...) sets; set_icon_color also covers notes, "
        "whose update_note takes no color."
    )
)
def set_icon_color(
    color: str,
    questline: int | None = None,
    note: int | None = None,
) -> dict[str, Any]:
    chosen = [(k, v) for k, v in (("questline", questline), ("note", note)) if v is not None]
    if len(chosen) != 1:
        raise ValueError("provide exactly one of: questline, note")
    hexval = (color or "").strip()
    if not hexval:
        raise ValueError("color must be a non-empty hex string like '#c47a20'")
    if not hexval.startswith("#"):
        hexval = f"#{hexval}"
    kind, owner_id = chosen[0]
    seg = {"questline": "questlines", "note": "notes"}[kind]
    return _api("PATCH", f"/api/{seg}/{owner_id}", body={"color": hexval})


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
