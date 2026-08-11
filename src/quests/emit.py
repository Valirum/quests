"""Stage durable changelog in the same session as domain writes, then publish.

Pattern for mutations::

    staged = stage_quest_diff(session, before, after, quiet=quiet, source=source)
    await session.commit()
    await deliver_staged(staged)

``hub.publish`` only fans out to WebSocket clients and hooks — it must not open
another SQLite writer.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from quests.changelog import stage_event
from quests.events import hub
from quests.models import QuestRead
from quests.notify import quest_change_events


def stage_quest_diff(
    session: AsyncSession,
    before: QuestRead,
    after: QuestRead,
    *,
    quiet: bool = False,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Add changelog rows for a quest diff; return kwargs for ``deliver_staged``."""
    out: list[dict[str, Any]] = []
    for ev in quest_change_events(before, after):
        toast = False if quiet else bool(ev.get("toast", True))
        kwargs: dict[str, Any] = {
            "kind": ev["kind"],
            "quest_id": after.id,
            "title": ev.get("title", after.title),
            "description": ev.get("description", after.description or ""),
            "detail": ev.get("detail", ""),
            "sound": ev.get("sound"),
            "toast": toast,
            "step_title": ev.get("step_title"),
            "significance": ev.get("significance"),
            "source": source,
        }
        stage_event(
            session,
            kind=str(kwargs["kind"]),
            quest_id=after.id,
            title=str(kwargs.get("title") or ""),
            detail=str(kwargs.get("detail") or ""),
            significance=kwargs.get("significance"),
        )
        out.append(kwargs)
    return out


def stage_simple(
    session: AsyncSession,
    *,
    kind: str,
    quest_id: int | None = None,
    title: str = "",
    detail: str = "",
    significance: Any = None,
    sound: str | None = None,
    toast: bool = True,
    source: str | None = None,
    description: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Stage one changelog row; return kwargs for ``deliver_staged`` after commit."""
    stage_event(
        session,
        kind=kind,
        quest_id=quest_id,
        title=title,
        detail=detail,
        significance=significance,
    )
    return {
        "kind": kind,
        "quest_id": quest_id,
        "title": title,
        "description": description,
        "detail": detail,
        "sound": sound,
        "toast": toast,
        "significance": significance,
        "source": source,
        **extra,
    }


async def deliver_staged(staged: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Publish pre-staged event kwargs (WS + hooks only)."""
    published: list[dict[str, Any]] = []
    for raw in staged:
        kwargs = dict(raw)
        kind = str(kwargs.pop("kind"))
        published.append(hub.publish(kind, **kwargs))
    return published
