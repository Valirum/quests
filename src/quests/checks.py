"""Auto-progress steps via optional shell check commands.

A step with ``check_command`` + ``check_interval_seconds`` is polled by the
server: command stdout is parsed as an int and written to ``progress_current``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from quests.db import SessionLocal, quest_load_options
from quests.emit import deliver_staged, stage_quest_diff
from quests.hero import apply_quest_status_rewards
from quests.models import Quest, QuestStatus, utcnow
from quests.progress import clamp_step_progress, sync_status_from_steps
from quests.serializers import quest_to_read
from quests.timeutil import ensure_utc, to_db_utc

log = logging.getLogger("quests.checks")

MIN_INTERVAL_SEC = 15
COMMAND_TIMEOUT_SEC = 60


def parse_check_output(stdout: str) -> int | None:
    """Parse an integer from command stdout (last line, or last int token)."""
    text = (stdout or "").strip()
    if not text:
        return None
    line = text.splitlines()[-1].strip()
    try:
        return int(line)
    except ValueError:
        pass
    nums = re.findall(r"-?\d+", line)
    if not nums:
        return None
    try:
        return int(nums[-1])
    except ValueError:
        return None


def normalize_check_fields(step: Any) -> None:
    """Empty command clears interval; bare interval without command is cleared."""
    cmd = (getattr(step, "check_command", None) or "").strip() or None
    step.check_command = cmd
    if cmd is None:
        step.check_interval_seconds = None
        return
    interval = getattr(step, "check_interval_seconds", None)
    if interval is None:
        return
    step.check_interval_seconds = max(MIN_INTERVAL_SEC, int(interval))


def step_check_due(step: Any, *, now: datetime | None = None) -> bool:
    cmd = (step.check_command or "").strip()
    if not cmd:
        return False
    interval = step.check_interval_seconds
    if interval is None or int(interval) < 1:
        return False
    interval = max(MIN_INTERVAL_SEC, int(interval))
    now_utc = ensure_utc(now) or datetime.now(timezone.utc)
    last = ensure_utc(step.check_last_run_at)
    if last is None:
        return True
    return (now_utc - last).total_seconds() >= interval


def run_check_command(command: str, *, timeout: float = COMMAND_TIMEOUT_SEC) -> int | None:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("check command failed: %s (%s)", command, exc)
        return None
    value = parse_check_output(proc.stdout or "")
    if value is None and proc.returncode != 0:
        log.warning(
            "check command exit %s: %s :: %s",
            proc.returncode,
            command,
            (proc.stderr or "").strip()[:200],
        )
    return value


async def run_due_step_checks(
    session: AsyncSession | None = None,
) -> list[int]:
    """Run due step checks. Returns quest ids whose progress changed."""
    owns = session is None
    if owns:
        session = SessionLocal()
    assert session is not None
    changed_ids: list[int] = []
    try:
        result = await session.exec(
            select(Quest)
            .where(Quest.status.in_([QuestStatus.active, QuestStatus.delayed]))
            .options(*quest_load_options())
        )
        quests = list(result.all())
        now = datetime.now(timezone.utc)

        for quest in quests:
            before = quest_to_read(quest)
            stamped = False
            progress_changed = False
            for step in list(quest.steps or []):
                normalize_check_fields(step)
                if not step_check_due(step, now=now):
                    continue
                cmd = (step.check_command or "").strip()
                value = await asyncio.to_thread(run_check_command, cmd)
                step.check_last_run_at = to_db_utc(now)
                stamped = True
                if value is None:
                    continue
                if int(step.progress_current) != int(value):
                    step.progress_current = int(value)
                    clamp_step_progress(step)
                    progress_changed = True

            if not stamped:
                continue

            if progress_changed:
                before_status = quest.status
                sync_status_from_steps(quest)
                if before_status != quest.status:
                    await apply_quest_status_rewards(
                        session, quest, new_status=quest.status
                    )
                quest.updated_at = utcnow()
            session.add(quest)
            qid = quest.id
            assert qid is not None

            staged: list = []
            if progress_changed:
                after = quest_to_read(quest)
                staged = stage_quest_diff(
                    session, before, after, quiet=False, source="system"
                )
                changed_ids.append(int(qid))

            await session.commit()
            await deliver_staged(staged)
        return changed_ids
    finally:
        if owns:
            await session.close()
