"""Quests MCP (stdio) — read-only tools over the HTTP API.

Configure Cursor (example)::

    {
      "mcpServers": {
        "quests": {
          "command": "uv",
          "args": ["run", "--directory", "/path/to/Quests", "quests-mcp"],
          "env": { "QUESTS_API": "http://192.168.1.11:8765" }
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

server = MCPServer(
    "quests",
    instructions=(
        "Read-only Quests journal tools. Prefer get_context with a pasted "
        "ref like quest=23 / step=252 / questline=3 (or the matching id field). "
        "Use list_questlines then list_quests to browse; get_context for full "
        "related detail (line + sibling quests + steps)."
    ),
)


def _api_get(path: str, query: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    if query:
        q = {k: v for k, v in query.items() if v is not None}
        if q:
            url = f"{url}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
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
