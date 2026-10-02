"""Fantasy presentation pack — parchment / journal tone."""

from __future__ import annotations

from overlay.stylepacks._css import render_css

PACK_ID = "fantasy"
PACK_LABEL = "Fantasy Journal"

# System mono (Nerd Font build is what most Arch/Cachy installs ship).
FONT_DISPLAY = '"JetBrainsMono Nerd Font", "JetBrains Mono", "JetBrainsMono NF", monospace'
FONT_BODY = FONT_DISPLAY
# Major / minor toasts — system serif (confirmed present on Cachy/Arch).
FONT_TOAST = '"Noto Serif", "Liberation Serif", "DejaVu Serif", serif'
# Persistent event log — mono reads cleaner for dense one-liners.
FONT_LOG = FONT_BODY

# Passthrough background tint (RGB); alpha comes from overlay settings.
PASSTHROUGH_BG_RGB = (26, 21, 16)
PASSTHROUGH_RADIUS = 8

# AFK major-toast glow (driven by sine from toast.py).
AFK_SIG_RGB = {
    "common": (168, 168, 168),
    "uncommon": (142, 192, 124),
    "epic": (211, 134, 155),
    "legendary": (254, 128, 25),
}
AFK_BORDER_RADIUS = 8
AFK_BORDER_WIDTH = 2
AFK_BORDER_LEFT_WIDTH = 2

# Timing (ms) — presentation contract; hosts should honor these.
MAJOR_FADE_IN_MS = 500
MAJOR_FADE_OUT_MS = 5000
MAJOR_HOLD_MS = 1200
MINOR_FADE_IN_MS = 280
MINOR_FADE_OUT_MS = 400
MINOR_HOLD_MS = 3200


def build_css() -> str:
    return render_css("fantasy.css", {**globals(), **locals()})
