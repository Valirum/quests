from __future__ import annotations

from quests.models import QuestRead, QuestStatus, SIGNIFICANCE_LABEL_RU


def _step_key(step) -> tuple:
    return (step.sort_order, step.title)


def significance_value(quest: QuestRead | None) -> str:
    if quest is None:
        return "common"
    sig = quest.significance
    if hasattr(sig, "value"):
        return str(sig.value)
    return str(sig or "common")


def _with_sig(event: dict, quest: QuestRead) -> dict:
    event["significance"] = significance_value(quest)
    return event


def _status_value(status) -> str:
    if hasattr(status, "value"):
        return str(status.value)
    return str(status or "")


def _describe_edits(before: QuestRead, after: QuestRead) -> list[str]:
    """Human-readable field diffs (excludes status/pin — those have own kinds)."""
    bits: list[str] = []
    if before.title != after.title:
        bits.append(f"название: «{before.title}» → «{after.title}»")
    if (before.description or "") != (after.description or ""):
        bits.append("описание")
    if significance_value(before) != significance_value(after):
        bits.append(
            f"значимость: {significance_value(before)} → {significance_value(after)}"
        )
    if before.deadline_at != after.deadline_at:
        bits.append("дедлайн")
    if before.duration_seconds != after.duration_seconds:
        bits.append("окно")
    if before.category_id != after.category_id:
        bits.append("раздел")
    if before.questline_id != after.questline_id:
        bits.append("квестлайн")
    if (before.reward_attrs or "") != (after.reward_attrs or ""):
        bits.append("награды")
    if before.sort_order != after.sort_order:
        bits.append("порядок")

    before_steps = list(before.steps or [])
    after_steps = list(after.steps or [])
    before_keys = {_step_key(s) for s in before_steps}
    after_keys = {_step_key(s) for s in after_steps}
    added = after_keys - before_keys
    removed = before_keys - after_keys
    if added:
        bits.append(f"+шаги: {len(added)}")
    if removed:
        bits.append(f"−шаги: {len(removed)}")
    # Renames / check-command edits that keep sort_order+title key won't show;
    # structural add/remove covers most step edits from the replace-all PATCH.
    return bits


def quest_change_events(before: QuestRead, after: QuestRead) -> list[dict]:
    """Derive notice events from a quest update."""
    events: list[dict] = []
    desc = after.description or ""

    if before.status != after.status:
        if after.status == QuestStatus.completed:
            events.append(
                _with_sig(
                    {
                        "kind": "quest_completed",
                        "title": after.title,
                        "description": desc,
                        "detail": after.progress_label,
                        "sound": "quest_completed",
                        "toast": True,
                    },
                    after,
                )
            )
        elif after.status == QuestStatus.failed:
            events.append(
                _with_sig(
                    {
                        "kind": "quest_failed",
                        "title": after.title,
                        "description": desc,
                        "detail": after.progress_label,
                        "sound": "quest_failed",
                        "toast": True,
                    },
                    after,
                )
            )
        elif after.status == QuestStatus.delayed:
            events.append(
                _with_sig(
                    {
                        "kind": "quest_delayed",
                        "title": after.title,
                        "detail": (
                            f"{_status_value(before.status)} → delayed"
                        ),
                        "sound": "quest_delayed",
                        "toast": True,
                    },
                    after,
                )
            )
        else:
            events.append(
                _with_sig(
                    {
                        "kind": "status_changed",
                        "title": after.title,
                        "detail": (
                            f"{_status_value(before.status)} → "
                            f"{_status_value(after.status)}"
                        ),
                        "sound": "status_changed",
                        "toast": True,
                    },
                    after,
                )
            )

    before_map = {_step_key(s): s for s in before.steps}
    for step in after.steps:
        old = before_map.get(_step_key(step))
        if old is None:
            continue
        became_done = (not bool(old.done)) and bool(step.done)
        progressed = step.progress_current > old.progress_current
        if became_done:
            events.append(
                _with_sig(
                    {
                        "kind": "step_completed",
                        "title": after.title,
                        "detail": (
                            f"{step.title} "
                            f"({step.progress_current}/{step.progress_total})"
                        ),
                        "sound": "step_completed",
                        "step_title": step.title,
                        "toast": True,
                    },
                    after,
                )
            )
        elif progressed:
            # Live refresh only; durable log skips step_progress.
            events.append(
                _with_sig(
                    {
                        "kind": "step_progress",
                        "title": after.title,
                        "detail": (
                            f"{step.title}: "
                            f"{step.progress_current}/{step.progress_total}"
                        ),
                        "sound": "step_progress",
                        "step_title": step.title,
                        "toast": False,
                    },
                    after,
                )
            )

    if before.pinned != after.pinned:
        events.append(
            _with_sig(
                {
                    "kind": "pin_changed",
                    "title": after.title,
                    "detail": "Pinned" if after.pinned else "Unpinned",
                    "sound": "pin_changed",
                    "toast": False,
                },
                after,
            )
        )

    edits = _describe_edits(before, after)
    if edits:
        events.append(
            _with_sig(
                {
                    "kind": "quest_updated",
                    "title": after.title,
                    "detail": ", ".join(edits)[:500],
                    "sound": "quest_updated",
                    "toast": False,
                },
                after,
            )
        )
    elif not events:
        events.append(
            _with_sig(
                {
                    "kind": "quest_updated",
                    "title": after.title,
                    "detail": after.progress_label,
                    "sound": "quest_updated",
                    "toast": False,
                },
                after,
            )
        )

    return events


def significance_label_ru(significance: str | None) -> str:
    key = (significance or "common").strip() or "common"
    return SIGNIFICANCE_LABEL_RU.get(key, SIGNIFICANCE_LABEL_RU["common"])
