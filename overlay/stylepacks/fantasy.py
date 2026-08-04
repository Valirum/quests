"""Fantasy presentation pack — parchment / journal tone."""

from __future__ import annotations

PACK_ID = "fantasy"
PACK_LABEL = "Fantasy Journal"

# System mono (Nerd Font build is what most Arch/Cachy installs ship).
FONT_DISPLAY = '"JetBrainsMono Nerd Font", "JetBrains Mono", "JetBrainsMono NF", monospace'
FONT_BODY = FONT_DISPLAY

# Passthrough background tint (RGB); alpha comes from overlay settings.
PASSTHROUGH_BG_RGB = (26, 21, 16)
PASSTHROUGH_RADIUS = 8

# Timing (ms) — presentation contract; hosts should honor these.
MAJOR_FADE_IN_MS = 500
MAJOR_FADE_OUT_MS = 5000
MAJOR_HOLD_MS = 1200
MINOR_FADE_IN_MS = 280
MINOR_FADE_OUT_MS = 400
MINOR_HOLD_MS = 3200


def build_css() -> str:
    return f"""
window {{
  background-color: rgba(0, 0, 0, 0);
  background-image: none;
}}

window.hud-window--interactive {{
  background-color: rgba(26, 21, 16, 0.72);
  border: 1px solid rgba(196, 165, 116, 0.4);
  border-radius: 8px;
}}

box {{
  background-color: transparent;
}}

/* —— HUD: text+shadow in passthrough; solid panel only when interactive —— */
box.hud {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  min-width: 0;
  font-family: {FONT_BODY};
}}

box.hud.hud--interactive {{
  /* Panel paint is on window.hud-window--interactive (layer-shell). */
  padding: 12px 14px;
  min-width: 280px;
}}

.hud-chip {{
  background-color: rgba(26, 21, 16, 0.6);
  border: none;
  border-radius: 0;
  padding: 2px 6px;
  text-shadow:
    0 0 3px rgba(0, 0, 0, 0.9),
    0 1px 2px rgba(0, 0, 0, 0.85);
}}

/* Panel already paints the plate — chips stay bare in interactive. */
.hud--interactive .hud-chip {{
  background-color: transparent;
  border-radius: 0;
  padding: 0;
  text-shadow: none;
}}

.hud-header {{
  margin-bottom: 2px;
}}

.hud-header-controls {{
  margin: 0;
  padding: 2px 4px;
}}

.hud-section {{
  margin-top: 0;
}}

.title {{
  color: #e8d5b0;
  font-family: {FONT_DISPLAY};
  font-size: 13pt;
  font-weight: 700;
  letter-spacing: 1px;
}}

.section-title {{
  color: #f0c86a;
  font-family: {FONT_DISPLAY};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.06em;
}}

.section-title-btn {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  color: #f0c86a;
  font-family: {FONT_DISPLAY};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.06em;
}}

.section-title-btn:hover {{
  color: #ffd978;
  background-color: transparent;
}}

.section-title-btn:active {{
  color: #c4a574;
  background-color: transparent;
}}

.section-rule {{
  min-height: 1px;
  min-width: 160px;
  background-color: rgba(196, 165, 116, 0.55);
  margin: 2px 0 6px;
}}

.section-rule--heavy {{
  min-height: 3px;
  min-width: 200px;
  background-color: rgba(240, 200, 106, 0.75);
  margin: 4px 0;
}}

.quest-timer {{
  font-family: {FONT_BODY};
  font-size: 10pt;
  font-weight: 700;
  font-feature-settings: "tnum";
}}

.quest-timer--green {{
  color: #8ec07c;
}}

.quest-timer--orange {{
  color: #fe8019;
}}

.quest-timer--red {{
  color: #fb4934;
}}

button.hud-icon-btn {{
  color: #c4a574;
  font-family: {FONT_BODY};
  font-size: 13pt;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1;
  min-width: 1.6em;
  min-height: 1.6em;
  padding: 2px 4px;
  margin: 0;
  background: none;
  background-color: transparent;
  border: none;
  border-radius: 4px;
  box-shadow: none;
  outline: none;
  opacity: 0.72;
}}

button.hud-icon-btn:hover {{
  color: #fff1d0;
  background-color: rgba(196, 165, 116, 0.18);
  opacity: 1;
}}

button.hud-icon-btn:active {{
  color: #c4a574;
  background-color: rgba(196, 165, 116, 0.28);
  opacity: 1;
}}

button.hud-icon-btn:focus {{
  box-shadow: none;
  outline: none;
}}

.hud-settings-panel {{
  min-width: 260px;
  padding: 2px 0 4px;
}}

.hud-settings-label {{
  color: #c4a574;
  font-family: {FONT_BODY};
  font-size: 9pt;
  font-weight: 600;
  letter-spacing: 0.04em;
}}

.hud-settings-hint {{
  font-size: 8pt;
  opacity: 0.75;
}}

.hud-opt-slider {{
  border: 1px solid rgba(196, 165, 116, 0.35);
  border-radius: 5px;
  overflow: hidden;
  background-color: rgba(20, 16, 12, 0.45);
}}

button.hud-opt {{
  color: #e8d5b0;
  font-family: {FONT_BODY};
  font-size: 9pt;
  font-weight: 500;
  letter-spacing: 0.02em;
  min-width: 0;
  min-height: 0;
  padding: 6px 10px;
  margin: 0;
  border: none;
  border-radius: 0;
  border-right: 1px solid rgba(196, 165, 116, 0.22);
  background: none;
  background-color: transparent;
  box-shadow: none;
  outline: none;
}}

button.hud-opt--last {{
  border-right: none;
}}

button.hud-opt:hover {{
  color: #fff1d0;
  background-color: rgba(196, 165, 116, 0.14);
}}

button.hud-opt--on {{
  color: #fff1d0;
  background-color: rgba(196, 165, 116, 0.28);
  font-weight: 700;
}}

button.hud-opt--on:hover {{
  background-color: rgba(196, 165, 116, 0.34);
}}

.hud-settings-scale {{
  color: #e8d5b0;
  font-family: {FONT_BODY};
  font-size: 9pt;
  margin-top: 2px;
}}

.hud-settings-scale trough {{
  min-height: 6px;
  border-radius: 3px;
  background-color: rgba(196, 165, 116, 0.18);
}}

.hud-settings-scale highlight {{
  background-color: rgba(196, 165, 116, 0.55);
  border-radius: 3px;
}}

.hud-settings-scale slider {{
  min-width: 12px;
  min-height: 12px;
  border-radius: 6px;
  background-color: #c4a574;
  border: none;
  box-shadow: none;
}}

button.hud-drag {{
  color: #c4a574;
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
  opacity: 0.85;
}}

button.hud-drag:hover,
button.hud-drag:active,
button.hud-drag:focus,
button.hud-drag:checked,
button.hud-drag:selected {{
  color: #c4a574;
  background: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  outline: none;
  opacity: 0.85;
}}

.quest {{
  padding: 0;
}}

.quest-title {{
  color: #f0e6d2;
  font-size: 11pt;
}}

.quest-progress {{
  color: rgba(232, 213, 176, 0.95);
  font-size: 9pt;
  font-feature-settings: "tnum";
}}

.hint {{
  color: rgba(232, 213, 176, 0.7);
  font-size: 8pt;
}}

/* —— Major notice (center; chip highlight under text only) —— */
.notice-root {{
  background-color: rgba(0, 0, 0, 0);
}}

.major {{
  background-color: rgba(26, 21, 16, 0.4);
  border: none;
  border-radius: 8px;
  padding: 36px 48px 40px;
  font-family: {FONT_BODY};
  text-shadow:
    0 0 4px rgba(0, 0, 0, 0.9),
    0 1px 3px rgba(0, 0, 0, 0.85);
}}

.major__eyebrow {{
  font-family: {FONT_DISPLAY};
  font-size: 22pt;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(250, 189, 47, 0.95);
  margin-bottom: 0;
}}

.major__eyebrow-row {{
  margin-bottom: 12px;
}}

.major__significance--common {{
  color: rgba(168, 168, 168, 0.95);
}}

.major__significance--uncommon {{
  color: rgba(142, 192, 124, 0.98);
}}

.major__significance--epic {{
  color: rgba(211, 134, 155, 0.98);
}}

.major__significance--legendary {{
  color: rgba(254, 128, 25, 0.98);
}}

.major--quest_completed .major__eyebrow:not(.major__significance) {{
  color: rgba(184, 187, 38, 0.95);
}}

.major--quest_failed .major__eyebrow:not(.major__significance) {{
  color: rgba(251, 73, 52, 0.95);
}}

.major__title {{
  font-family: {FONT_DISPLAY};
  font-size: 44pt;
  font-weight: 700;
  color: #f0e6d2;
}}

.major__rule {{
  min-height: 2px;
  background-color: rgba(232, 213, 176, 0.55);
  margin: 20px 0;
  border: none;
}}

.major__description {{
  font-size: 24pt;
  line-height: 1.45;
  color: rgba(232, 213, 176, 0.88);
}}

.major__detail {{
  font-size: 20pt;
  color: rgba(196, 165, 116, 0.9);
  font-style: italic;
  margin-top: 12px;
}}

/* —— Minor toast (bottom-right) —— */
.minor {{
  min-width: 260px;
  padding: 12px 14px;
  border-radius: 6px;
  border: 1px solid rgba(196, 165, 116, 0.4);
  background-color: rgba(26, 21, 16, 0.88);
  font-family: {FONT_BODY};
}}

.minor__title {{
  font-family: {FONT_DISPLAY};
  font-size: 11pt;
  font-weight: 700;
  color: #f0e6d2;
}}

.minor__change {{
  font-size: 9pt;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(250, 189, 47, 0.9);
  margin-top: 4px;
}}

.minor__detail {{
  font-size: 9pt;
  color: rgba(196, 165, 116, 0.9);
  margin-top: 4px;
}}

.minor--step_completed .minor__change {{
  color: rgba(142, 192, 124, 0.95);
}}

.minor--quest_deleted .minor__change {{
  color: rgba(251, 73, 52, 0.9);
}}

.minor--quest_delayed .minor__change {{
  color: rgba(254, 128, 25, 0.95);
}}
"""
