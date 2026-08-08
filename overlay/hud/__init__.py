"""HUD panel, monitors, drag, and input-mode helpers."""

from .deadline import format_remaining, is_urgent, remaining_seconds, timer_tone
from .drag import NUDGE_STEP, attach_drag_handle, nudge_hud
from .input_mode import apply_hud_input_mode
from .monitors import (
    apply_monitor,
    cycle_index,
    focus_niri_output,
    list_monitors,
    monitor_connector,
    monitor_label,
    resolve_monitor_index,
)
from .panel import (
    HudQuest,
    HudStep,
    TimerBinding,
    apply_timer_bindings,
    build_hud,
    cycle_hud_category,
    resolve_hud_category,
    split_hud_quests,
)

__all__ = [
    "HudQuest",
    "HudStep",
    "NUDGE_STEP",
    "TimerBinding",
    "apply_hud_input_mode",
    "apply_monitor",
    "apply_timer_bindings",
    "attach_drag_handle",
    "build_hud",
    "cycle_hud_category",
    "cycle_index",
    "focus_niri_output",
    "format_remaining",
    "is_urgent",
    "list_monitors",
    "monitor_connector",
    "monitor_label",
    "nudge_hud",
    "remaining_seconds",
    "resolve_hud_category",
    "resolve_monitor_index",
    "split_hud_quests",
    "timer_tone",
]
