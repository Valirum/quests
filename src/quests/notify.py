from __future__ import annotations

from quests.models import QuestRead, QuestStatus


def _step_key(step) -> tuple:
    return (step.sort_order, step.title)


def quest_change_events(before: QuestRead, after: QuestRead) -> list[dict]:
    """Derive notice events from a quest update."""
    events: list[dict] = []
    desc = after.description or ""

    if before.status != after.status:
        if after.status == QuestStatus.completed:
            events.append(
                {
                    "kind": "quest_completed",
                    "title": after.title,
                    "description": desc,
                    "detail": after.progress_label,
                    "sound": "quest_completed",
                    "toast": True,
                }
            )
        elif after.status == QuestStatus.failed:
            events.append(
                {
                    "kind": "quest_failed",
                    "title": after.title,
                    "description": desc,
                    "detail": after.progress_label,
                    "sound": "quest_failed",
                    "toast": True,
                }
            )
        elif after.status == QuestStatus.delayed:
            events.append(
                {
                    "kind": "quest_delayed",
                    "title": after.title,
                    "detail": f"{before.status.value if hasattr(before.status,'value') else before.status} → delayed",
                    "sound": "quest_delayed",
                    "toast": True,
                }
            )
        else:
            events.append(
                {
                    "kind": "status_changed",
                    "title": after.title,
                    "detail": f"{before.status} → {after.status}",
                    "sound": "status_changed",
                    "toast": True,
                }
            )

    before_map = {_step_key(s): s for s in before.steps}
    for step in after.steps:
        old = before_map.get(_step_key(step))
        if old is None:
            continue
        became_done = (not old.done) and step.done
        progressed = step.progress_current > old.progress_current
        if became_done:
            events.append(
                {
                    "kind": "step_completed",
                    "title": after.title,
                    "detail": f"{step.title} ({step.progress_current}/{step.progress_total})",
                    "sound": "step_completed",
                    "step_title": step.title,
                    "toast": True,
                }
            )
        elif progressed:
            events.append(
                {
                    "kind": "step_progress",
                    "title": after.title,
                    "detail": f"{step.title}: {step.progress_current}/{step.progress_total}",
                    "sound": "step_progress",
                    "step_title": step.title,
                    "toast": False,
                }
            )

    if before.pinned != after.pinned:
        events.append(
            {
                "kind": "pin_changed",
                "title": after.title,
                "detail": "Pinned" if after.pinned else "Unpinned",
                "sound": "pin_changed",
                "toast": False,
            }
        )

    if not events:
        events.append(
            {
                "kind": "quest_updated",
                "title": after.title,
                "detail": after.progress_label,
                "sound": "quest_updated",
                "toast": False,
            }
        )

    return events
