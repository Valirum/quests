"""Cyberpunk 2077–inspired pack — hard edges, scanlines.

HUD: JOURNAL cyan · quest titles red · step lines yellow.
GTK can't do true clip-path chamfers; accents use hard borders instead.
"""

from __future__ import annotations

from overlay.stylepacks._css import render_css

PACK_ID = "cyberpunk"
PACK_LABEL = "Cyberpunk 2077"

# Condensed tech sans when available; fall back to clean system sans.
FONT_DISPLAY = (
    '"Rajdhani", "Oxanium", "Orbitron", "Noto Sans Display", '
    '"Noto Sans", "DejaVu Sans", sans-serif'
)
FONT_BODY = (
    '"Rajdhani", "Noto Sans", "DejaVu Sans", sans-serif'
)
# Major / minor toasts — system serif.
FONT_TOAST = '"Noto Serif", "Liberation Serif", "DejaVu Serif", serif'
# Persistent event log — mono (same stack as fantasy HUD).
FONT_LOG = (
    '"JetBrainsMono Nerd Font", "JetBrains Mono", "JetBrainsMono NF", monospace'
)

PASSTHROUGH_BG_RGB = (12, 12, 14)
PASSTHROUGH_RADIUS = 0

# AFK major-toast glow (driven by sine from toast.py).
AFK_SIG_RGB = {
    "common": (168, 168, 168),
    "uncommon": (61, 255, 154),
    "epic": (199, 125, 255),
    "legendary": (255, 138, 31),
}
AFK_BORDER_RADIUS = 0
AFK_BORDER_WIDTH = 2
AFK_BORDER_LEFT_WIDTH = 3

# Slightly snappier than fantasy — UI feels more "digital".
MAJOR_FADE_IN_MS = 280
MAJOR_FADE_OUT_MS = 4200
MAJOR_HOLD_MS = 1400
MINOR_FADE_IN_MS = 180
MINOR_FADE_OUT_MS = 320
MINOR_HOLD_MS = 2800

# Palette: JOURNAL cyan · quest titles red · steps yellow
YELLOW = "#fcee0a"
YELLOW_DIM = "#c4b808"
RED = "#e03131"
RED_HOT = "#ff003c"
CYAN = "#00f0ff"
CYAN_DIM = "#00b8c4"
INK = "rgba(8, 8, 10, 0.78)"
# Passthrough text plate — dark burgundy, light alpha
INK_SOFT = "rgba(48, 8, 18, 0.2)"
PLATE = "rgba(12, 12, 14, 0.72)"


def _scanlines(alpha: float = 0.07) -> str:
    """Faint CRT hatch over a layer."""
    return (
        f"repeating-linear-gradient("
        f"0deg, transparent, transparent 1px, rgba(0,0,0,{alpha}) 1px, "
        f"rgba(0,0,0,{alpha}) 2px)"
    )


def build_css() -> str:
    scan = _scanlines(0.08)
    scan_soft = _scanlines(0.05)
    return render_css("cyberpunk.css", {**globals(), **locals()})
