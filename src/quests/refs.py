"""Resolve category/questline given as numeric id or name/substring.

Shared by the MCP server and the LLM action executor — both need the same
"id, or name/substring against /api/categories|/api/questlines" convention
the Go CLI's ResolveCategoryID/ResolveQuestlineID already use.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ApiGet = Callable[[str], Any]


def is_none_token(raw: str) -> bool:
    return raw.strip().lower() in {"", "none", "-", "нет", "null"}


def resolve_ref_id(
    raw: str | int | None,
    *,
    path: str,
    needle_fields: tuple[str, ...],
    api_get: ApiGet,
) -> int | None:
    """Resolve a category/questline given as id, or as a name/substring
    (case-insensitive), the same way the CLI's Resolve*ID helpers do."""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if is_none_token(raw):
        return None
    text = raw.strip()
    if text.lstrip("-").isdigit():
        return int(text)
    needle = text.lower()
    rows = api_get(path) or []
    matches = [
        row["id"]
        for row in rows
        if any(
            needle == str(row.get(f, "")).lower()
            or needle in str(row.get(f, "")).lower()
            for f in needle_fields
        )
    ]
    exact = [
        row["id"]
        for row in rows
        if any(str(row.get(f, "")).lower() == needle for f in needle_fields)
    ]
    if exact:
        matches = exact
    if not matches:
        raise ValueError(f"{path.rsplit('/', 1)[-1]} {raw!r} not found")
    if len(matches) > 1:
        raise ValueError(f"multiple matches for {raw!r} in {path}; pass a numeric id")
    return matches[0]


def resolve_category_id(raw: str | int | None, *, api_get: ApiGet) -> int | None:
    return resolve_ref_id(
        raw, path="/api/categories", needle_fields=("slug", "label"), api_get=api_get
    )


def resolve_questline_id(raw: str | int | None, *, api_get: ApiGet) -> int | None:
    return resolve_ref_id(
        raw, path="/api/questlines", needle_fields=("title",), api_get=api_get
    )
