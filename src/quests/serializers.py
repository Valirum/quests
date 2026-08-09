from __future__ import annotations

from quests.models import Quest, QuestStep, QuestStepRead, QuestRead
from quests.questline_icons import icon_url as questline_icon_url
from quests.timeutil import (
    ensure_utc,
    is_in_urgent_window,
    remaining_seconds,
    timer_tone,
    to_utc_iso,
)


def step_to_read(step: QuestStep) -> QuestStepRead:
    return QuestStepRead(
        id=step.id,  # type: ignore[arg-type]
        quest_id=step.quest_id,
        title=step.title,
        description=step.description,
        progress_current=step.progress_current,
        progress_total=step.progress_total,
        sort_order=step.sort_order,
        check_command=step.check_command,
        check_interval_seconds=step.check_interval_seconds,
        check_last_run_at=ensure_utc(step.check_last_run_at),
        done=step.done,
    )


def quest_progress(steps: list[QuestStep]) -> tuple[int, int, str]:
    """Return (steps_done, steps_total, label).

    - One quantified step → "5 / 8"
    - Several steps → "2 / 3" by completion count
    """
    if not steps:
        return 0, 0, "0 / 0"

    ordered = sorted(steps, key=lambda s: (s.sort_order, s.id or 0))
    if len(ordered) == 1:
        s = ordered[0]
        return (
            1 if s.done else 0,
            1,
            f"{s.progress_current} / {s.progress_total}",
        )

    done = sum(1 for s in ordered if s.done)
    total = len(ordered)
    return done, total, f"{done} / {total}"


def quest_to_read(quest: Quest) -> QuestRead:
    steps = list(quest.steps or [])
    steps_done, steps_total, label = quest_progress(steps)
    deadline = ensure_utc(quest.deadline_at)
    rem = remaining_seconds(deadline)
    status_val = (
        quest.status.value if hasattr(quest.status, "value") else str(quest.status or "")
    )
    overdue = status_val == "delayed" or (rem is not None and rem <= 0)
    # Overdue / delayed: still urgent for HUD (same lane as near-deadline).
    if overdue:
        rem = None  # no negative countdown in API
        tone = "overdue"
        urgent = True
    else:
        tone = timer_tone(deadline, quest.duration_seconds)
        urgent = is_in_urgent_window(deadline, quest.duration_seconds)
    cat = getattr(quest, "category", None)
    line = getattr(quest, "questline", None)
    custom = getattr(line, "custom_icon", None) if line is not None else None
    line_id = getattr(line, "id", None) if line is not None else quest.questline_id
    q_icon_url = None
    if custom and line_id is not None:
        q_icon_url = questline_icon_url(
            int(line_id), version=to_utc_iso(getattr(line, "updated_at", None))
        )
    return QuestRead(
        id=quest.id,  # type: ignore[arg-type]
        title=quest.title,
        description=quest.description,
        status=quest.status,
        significance=quest.significance,
        pinned=quest.pinned,
        sort_order=quest.sort_order,
        deadline_at=deadline,
        duration_seconds=quest.duration_seconds,
        reward_attrs=quest.reward_attrs,
        category_id=quest.category_id,
        category_slug=getattr(cat, "slug", None) if cat is not None else None,
        category_label=getattr(cat, "label", None) if cat is not None else None,
        category_color=getattr(cat, "color", None) if cat is not None else None,
        questline_id=quest.questline_id,
        questline_title=getattr(line, "title", None) if line is not None else None,
        questline_color=getattr(line, "color", None) if line is not None else None,
        questline_icon=getattr(line, "icon", None) if line is not None else None,
        questline_icon_url=q_icon_url,
        created_at=ensure_utc(quest.created_at),  # type: ignore[arg-type]
        updated_at=ensure_utc(quest.updated_at),  # type: ignore[arg-type]
        completed_at=ensure_utc(quest.completed_at),
        template_id=quest.template_id,
        period_key=quest.period_key,
        steps=[step_to_read(s) for s in sorted(steps, key=lambda s: (s.sort_order, s.id or 0))],
        steps_done=steps_done,
        steps_total=steps_total,
        progress_label=label,
        remaining_seconds=rem,
        timer_tone=tone,
        urgent=urgent,
    )
