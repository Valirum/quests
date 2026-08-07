"""Sound cues for overlay. Plays random VO from assets/sounds/<cue>/."""

from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent / "assets" / "sounds"

# Event kind / sound cue → folder under assets/sounds/
CUE_FOLDERS = {
    "quest_created": "quest_appeared",
    "quest_appeared": "quest_appeared",
    "quest_started": "quest_appeared",
    "quest_completed": "quest_completed",
    "quest_failed": "quest_failed",
    "quest_delayed": "quest_delayed",
    "step_completed": "step_completed",
    "step_progress": "step_progress",
    "status_changed": "status_changed",
    "fallback": "fallback",
    "quest_updated": "fallback",
}

MAJOR_CUES = frozenset(
    {
        "quest_created",
        "quest_appeared",
        "quest_started",
        "quest_completed",
        "quest_failed",
        "quest_delayed",
    }
)


@dataclass
class SoundBus:
    enabled: bool = True
    last_cue: str | None = None
    history: list[str] = field(default_factory=list)
    _proc: subprocess.Popen | None = None

    def play(self, cue: str | None, *, source: str = "overlay", major_only: bool = False) -> None:
        if not cue or not self.enabled:
            return
        if major_only and cue not in MAJOR_CUES and CUE_FOLDERS.get(cue) not in {
            "quest_appeared",
            "quest_completed",
            "quest_failed",
            "quest_delayed",
        }:
            return

        self.last_cue = cue
        self.history.append(cue)
        if len(self.history) > 32:
            self.history = self.history[-32:]

        path = self._pick_file(cue)
        if path is None:
            return
        self._spawn(path)

    def _pick_file(self, cue: str) -> Path | None:
        folder = CUE_FOLDERS.get(cue, cue)
        directory = SOUNDS_DIR / folder
        if not directory.is_dir():
            return None
        files = sorted(directory.glob("*.mp3")) + sorted(directory.glob("*.ogg"))
        if not files:
            return None
        return random.choice(files)

    def _spawn(self, path: Path) -> None:
        # Stop previous line so majors don't overlap messily.
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        try:
            self._proc = subprocess.Popen(
                ["paplay", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            try:
                self._proc = subprocess.Popen(
                    ["mpv", "--no-video", "--really-quiet", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                pass


sounds = SoundBus()
