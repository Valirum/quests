"""Step progress helpers and auto status sync."""

from __future__ import annotations

from quests.models import Quest, QuestStatus, QuestStep, utcnow


def clamp_step_progress(step: QuestStep) -> None:
    total = max(1, int(step.progress_total))
    step.progress_total = total
    step.progress_current = max(0, min(int(step.progress_current), total))


def steps_all_done(quest: Quest) -> bool:
    steps = list(quest.steps or [])
    if not steps:
        return False
    return all(s.progress_current >= s.progress_total for s in steps)


def sync_status_from_steps(quest: Quest) -> None:
    """Complete when all steps done; reopen completed → active if any step undone."""
    steps = list(quest.steps or [])
    if not steps:
        return

    all_done = steps_all_done(quest)
    if all_done and quest.status in {
        QuestStatus.active,
        QuestStatus.delayed,
        QuestStatus.failed,
    }:
        quest.status = QuestStatus.completed
    elif not all_done and quest.status == QuestStatus.completed:
        quest.status = QuestStatus.active

    if quest.status == QuestStatus.completed and quest.completed_at is None:
        quest.completed_at = utcnow()
    if quest.status != QuestStatus.completed:
        quest.completed_at = None
