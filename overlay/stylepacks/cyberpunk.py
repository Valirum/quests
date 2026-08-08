"""Cyberpunk 2077–inspired pack — hard edges, scanlines.

HUD: JOURNAL cyan · quest titles red · step lines yellow.
GTK can't do true clip-path chamfers; accents use hard borders instead.
"""

from __future__ import annotations

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
    return f"""
window {{
  background-color: rgba(0, 0, 0, 0);
  background-image: none;
}}

window.hud-window--interactive {{
  background-color: {PLATE};
  background-image: {scan_soft};
  border: 1px solid rgba(252, 238, 10, 0.35);
  border-radius: 0;
}}

box {{
  background-color: transparent;
}}

/* —— HUD —— */
box.hud {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  min-width: 0;
  font-family: {FONT_BODY};
}}

box.hud.hud--interactive {{
  padding: 12px 14px;
  min-width: 280px;
}}

.hud-chip {{
  background-color: {INK_SOFT};
  background-image: {scan_soft};
  border: none;
  border-radius: 0;
  padding: 2px 7px;
  text-shadow:
    0 0 2px rgba(0, 0, 0, 0.95),
    1px 0 0 rgba(224, 49, 49, 0.25),
    -1px 0 0 rgba(0, 200, 255, 0.12);
}}

.hud--interactive .hud-chip {{
  background-color: transparent;
  background-image: none;
  padding: 0;
  text-shadow: none;
}}

.hud-header {{
  margin-bottom: 4px;
}}

.hud-header-controls {{
  margin: 0;
  padding: 2px 4px;
}}

.hud-section {{
  margin-top: 0;
}}

/* JOURNAL — cyan */
.title {{
  color: {CYAN};
  font-family: {FONT_DISPLAY};
  font-size: 14pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  text-shadow:
    0 1px 0 rgba(0, 0, 0, 0.85),
    0 0 8px rgba(0, 240, 255, 0.4);
}}

/* Quest titles — red */
.section-title {{
  color: {RED};
  font-family: {FONT_DISPLAY};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-shadow:
    0 0 2px rgba(0, 0, 0, 0.9),
    0 0 10px rgba(255, 0, 60, 0.3);
}}

.section-heading {{
  color: {CYAN};
  font-family: {FONT_DISPLAY};
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  text-shadow:
    0 0 2px rgba(0, 0, 0, 0.9),
    0 0 10px rgba(0, 240, 255, 0.35);
}}

.section-title-btn {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  color: {RED};
  font-family: {FONT_DISPLAY};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.02em;
}}

.section-title-btn:hover {{
  color: {RED_HOT};
  background-color: transparent;
}}

.section-title-btn:active {{
  color: #a02020;
  background-color: transparent;
}}

.section-rule {{
  min-height: 1px;
  min-width: 160px;
  background-color: rgba(224, 49, 49, 0.55);
  margin: 2px 0 6px;
  border-radius: 0;
}}

.section-rule--heavy {{
  min-height: 2px;
  min-width: 200px;
  background-color: rgba(0, 240, 255, 0.45);
  margin: 6px 0;
}}

.quest-timer {{
  font-family: {FONT_BODY};
  font-size: 10pt;
  font-weight: 700;
  font-feature-settings: "tnum";
  letter-spacing: 0.04em;
}}

.quest-timer--green {{
  color: #3dff9a;
}}

.quest-timer--orange {{
  color: {YELLOW};
}}

.quest-timer--red {{
  color: {RED_HOT};
}}

.quest-timer--overdue {{
  color: {RED_HOT};
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-shadow: 0 0 10px rgba(255, 0, 60, 0.45);
}}

button.hud-icon-btn {{
  color: {CYAN};
  font-family: {FONT_BODY};
  font-size: 13pt;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
  min-width: 1.6em;
  min-height: 1.6em;
  padding: 2px 4px;
  margin: 0;
  background: none;
  background-color: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
  outline: none;
  opacity: 0.75;
}}

button.hud-icon-btn:hover {{
  color: {YELLOW};
  background-color: rgba(252, 238, 10, 0.14);
  opacity: 1;
}}

button.hud-icon-btn:active {{
  color: #0a0a0c;
  background-color: {YELLOW};
  opacity: 1;
}}

button.hud-icon-btn:focus {{
  box-shadow: none;
  outline: none;
}}

.hud-settings-panel {{
  min-width: 280px;
  padding: 2px 0 4px;
}}

.hud-settings-label {{
  color: {CYAN};
  font-family: {FONT_BODY};
  font-size: 9pt;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}}

.hud-settings-section {{
  color: {YELLOW};
  font-family: {FONT_DISPLAY};
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-top: 6px;
  text-shadow: 0 0 8px rgba(252, 238, 10, 0.25);
}}

.hud-settings-hint {{
  font-size: 8pt;
  opacity: 0.7;
}}

.hud-opt-slider {{
  border: 1px solid rgba(252, 238, 10, 0.4);
  border-radius: 0;
  overflow: hidden;
  background-color: rgba(5, 5, 8, 0.55);
}}

button.hud-opt {{
  color: {YELLOW};
  font-family: {FONT_BODY};
  font-size: 8pt;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  min-width: 0;
  min-height: 0;
  padding: 7px 10px;
  margin: 0;
  border: none;
  border-radius: 0;
  border-right: 1px solid rgba(252, 238, 10, 0.22);
  background: none;
  background-color: transparent;
  box-shadow: none;
  outline: none;
}}

button.hud-opt--last {{
  border-right: none;
}}

button.hud-opt:hover {{
  color: #fff45a;
  background-color: rgba(252, 238, 10, 0.12);
}}

button.hud-opt--on {{
  color: {CYAN};
  background-color: rgba(5, 195, 221, 0.16);
}}

button.hud-opt--on:hover {{
  background-color: rgba(5, 195, 221, 0.22);
}}

.hud-settings-scale {{
  color: {YELLOW};
  font-family: {FONT_BODY};
  font-size: 9pt;
  margin-top: 2px;
}}

.hud-settings-scale trough {{
  min-height: 6px;
  border-radius: 0;
  background-color: rgba(252, 238, 10, 0.16);
}}

.hud-settings-scale highlight {{
  background-color: {CYAN};
  border-radius: 0;
}}

.hud-settings-scale slider {{
  min-width: 12px;
  min-height: 12px;
  border-radius: 0;
  background-color: {YELLOW};
  border: none;
  box-shadow: none;
}}

button.hud-drag {{
  color: rgba(224, 49, 49, 0.85);
  font-family: {FONT_BODY};
  font-size: 11pt;
  letter-spacing: 0;
  line-height: 1;
  min-width: 0;
  min-height: 0;
  padding: 2px 4px;
  margin: 0;
  background: none;
  background-color: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
  outline: none;
  opacity: 0.9;
}}

button.hud-drag:hover,
button.hud-drag:active,
button.hud-drag:focus,
button.hud-drag:checked,
button.hud-drag:selected {{
  color: rgba(224, 49, 49, 0.85);
  background: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  outline: none;
  opacity: 0.9;
}}

.quest {{
  padding: 0;
}}

/* Steps / items — yellow */
.quest-title {{
  color: {YELLOW};
  font-size: 10pt;
  font-weight: 600;
  text-shadow: 0 0 6px rgba(252, 238, 10, 0.2);
}}

.quest-progress {{
  color: {YELLOW};
  font-size: 9pt;
  font-weight: 700;
  font-feature-settings: "tnum";
}}

.hint {{
  color: {CYAN_DIM};
  font-size: 8pt;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}

/* —— Major notice —— */
.notice-root {{
  background-color: rgba(0, 0, 0, 0);
}}

.major {{
  background-color: {INK};
  background-image: {scan};
  border: 1px solid rgba(252, 238, 10, 0.4);
  border-left: 3px solid {YELLOW};
  border-radius: 0;
  padding: 32px 44px 36px;
  font-family: {FONT_TOAST};
  text-shadow:
    0 0 3px rgba(0, 0, 0, 0.95),
    1px 0 0 rgba(224, 49, 49, 0.2);
}}

.major__eyebrow {{
  font-family: {FONT_TOAST};
  font-size: 18pt;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: {RED};
  margin-bottom: 0;
  text-shadow:
    0 1px 0 rgba(0, 0, 0, 0.9),
    0 0 12px rgba(255, 0, 60, 0.4);
}}

.major__eyebrow-row {{
  margin-bottom: 10px;
}}

.major__significance--common {{
  color: #a8a8a8;
  text-shadow: 0 0 8px rgba(168, 168, 168, 0.25);
}}

.major__significance--uncommon {{
  color: #3dff9a;
  text-shadow: 0 0 12px rgba(61, 255, 154, 0.45);
}}

.major__significance--epic {{
  color: #c77dff;
  text-shadow: 0 0 12px rgba(199, 125, 255, 0.45);
}}

.major__significance--legendary {{
  color: #ff8a1f;
  text-shadow: 0 0 14px rgba(255, 138, 31, 0.5);
}}

.major--quest_completed .major__eyebrow:not(.major__significance) {{
  color: #3dff9a;
  text-shadow: 0 0 12px rgba(61, 255, 154, 0.4);
}}

.major--quest_failed .major__eyebrow:not(.major__significance) {{
  color: {RED_HOT};
}}

.major--quest_delayed .major__eyebrow:not(.major__significance) {{
  color: {RED_HOT};
}}

.major--quest_started .major__eyebrow:not(.major__significance) {{
  color: {CYAN};
}}

.major__title {{
  font-family: {FONT_TOAST};
  font-size: 36pt;
  font-weight: 700;
  color: {YELLOW};
  letter-spacing: 0.02em;
  text-shadow:
    0 0 2px rgba(0, 0, 0, 0.95),
    0 0 18px rgba(252, 238, 10, 0.3);
}}

.major__rule {{
  min-height: 2px;
  background-color: rgba(224, 49, 49, 0.7);
  margin: 16px 0;
  border: none;
  border-radius: 0;
}}

.major__description {{
  font-size: 18pt;
  line-height: 1.4;
  font-weight: 600;
  color: rgba(240, 240, 242, 0.9);
}}

.major__detail {{
  font-size: 14pt;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: {RED};
  margin-top: 12px;
}}

/* —— Minor toast (objective plate) —— */
.minor {{
  min-width: 280px;
  padding: 12px 14px 12px 16px;
  border-radius: 0;
  border: 1px solid rgba(252, 238, 10, 0.45);
  border-left: 3px solid {YELLOW};
  background-color: {INK};
  background-image:
    linear-gradient(135deg, transparent 8px, transparent 8px),
    {_scanlines(0.06)};
  font-family: {FONT_TOAST};
}}

.minor__title {{
  font-family: {FONT_TOAST};
  font-size: 12pt;
  font-weight: 700;
  color: {YELLOW};
  letter-spacing: 0.01em;
  text-shadow: 0 0 8px rgba(252, 238, 10, 0.25);
}}

.minor__change {{
  font-size: 9pt;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: {RED};
  margin-top: 4px;
}}

.minor__detail {{
  font-size: 9pt;
  color: rgba(220, 220, 222, 0.75);
  margin-top: 4px;
}}

.minor--step_completed .minor__change {{
  color: #3dff9a;
}}

.minor--quest_deleted .minor__change,
.minor--quest_failed .minor__change {{
  color: {RED_HOT};
}}

.minor--quest_delayed .minor__change {{
  color: {YELLOW};
}}

/* —— Minor event log (one line) —— */
.minor-log {{
  min-width: 0;
  max-width: none;
  padding: 8px 10px 8px 12px;
  font-family: {FONT_TOAST};
}}

.minor-log__empty {{
  font-size: 9pt;
  color: rgba(220, 220, 222, 0.55);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}

.minor-log__row {{
  padding: 1px 6px;
  margin: 0;
  border-left: 2px solid rgba(252, 238, 10, 0.28);
}}

.minor-log__ts {{
  font-size: 9pt;
  font-family: {FONT_BODY};
  color: rgba(220, 220, 222, 0.85);
  letter-spacing: 0.04em;
}}

.minor-log__sep {{
  font-size: 9pt;
  color: rgba(220, 220, 222, 0.85);
}}

.minor-log__title {{
  font-size: 9pt;
  font-weight: 700;
  color: {YELLOW};
}}

.minor-log__title--common {{
  color: rgba(168, 168, 168, 0.95);
}}

.minor-log__title--uncommon {{
  color: #3dff9a;
}}

.minor-log__title--epic {{
  color: #ff6ec7;
}}

.minor-log__title--legendary {{
  color: #ff8a1f;
}}

.minor-log__msg {{
  font-size: 9pt;
  color: rgba(220, 220, 222, 0.7);
}}

.minor-log__msg--step_completed,
.minor-log__msg--quest_completed {{
  color: #3dff9a;
}}

.minor-log__msg--quest_deleted,
.minor-log__msg--quest_failed {{
  color: {RED_HOT};
}}

.minor-log__msg--quest_delayed {{
  color: {YELLOW};
}}

.minor-log__msg--pin_changed {{
  color: {CYAN};
}}

.minor-log__msg--status_changed {{
  color: #ff6ec7;
}}

.minor-log__msg--quest_created,
.minor-log__msg--quest_appeared {{
  color: {YELLOW};
}}

.minor-log__msg--quest_updated {{
  color: rgba(220, 220, 222, 0.72);
}}

.minor-log__row--step_completed,
.minor-log__row--quest_completed {{
  border-left-color: #3dff9a;
}}

.minor-log__row--quest_deleted,
.minor-log__row--quest_failed {{
  border-left-color: {RED_HOT};
}}
"""
