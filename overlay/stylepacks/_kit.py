"""Shared modern HUD/toast CSS builder for palette-driven style packs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackTheme:
    """Color + typography tokens for a modern (non-cyber) pack."""

    pack_id: str
    label: str
    font_display: str
    font_body: str
    font_toast: str
    font_log: str
    # RGB for passthrough plate
    bg_rgb: tuple[int, int, int]
    radius: int = 8
    # Core colors (hex)
    fg: str = "#ebdbb2"
    fg_muted: str = "#a89984"
    fg_dim: str = "#928374"
    accent: str = "#b8bb26"
    accent_hot: str = "#98971a"
    accent_soft: str = "#d5c4a1"
    title: str = "#ebdbb2"
    section: str = "#b8bb26"
    border: str = "#504945"
    ok: str = "#8ec07c"
    warn: str = "#fe8019"
    danger: str = "#fb4934"
    info: str = "#83a598"
    sig_common: str = "#a89984"
    sig_uncommon: str = "#8ec07c"
    sig_epic: str = "#83a598"
    sig_legendary: str = "#fabd2f"
    # Timing
    major_fade_in_ms: int = 420
    major_fade_out_ms: int = 4800
    major_hold_ms: int = 1200
    minor_fade_in_ms: int = 240
    minor_fade_out_ms: int = 360
    minor_hold_ms: int = 3000
    # AFK glow RGB
    afk_common: tuple[int, int, int] = (168, 168, 168)
    afk_uncommon: tuple[int, int, int] = (142, 192, 124)
    afk_epic: tuple[int, int, int] = (131, 165, 152)
    afk_legendary: tuple[int, int, int] = (250, 189, 47)
    letter_spacing_title: str = "0.04em"
    uppercase_section: bool = True


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def _rgb_tuple(rgb: tuple[int, int, int], alpha: float) -> str:
    r, g, b = rgb
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def build_modern_css(t: PackTheme) -> str:
    """Fantasy-shaped modern pack CSS from a theme palette."""
    r, g, b = t.bg_rgb
    plate = _rgb_tuple(t.bg_rgb, 0.72)
    chip = _rgb_tuple(t.bg_rgb, 0.55)
    ink_soft = _rgb_tuple(t.bg_rgb, 0.45)
    rad = int(t.radius)
    rad_sm = max(0, rad - 2)
    rad_btn = max(2, rad // 2)
    section_transform = "uppercase" if t.uppercase_section else "none"
    section_tracking = "0.12em" if t.uppercase_section else "0.04em"

    return f"""
window {{
  background-color: rgba(0, 0, 0, 0);
  background-image: none;
}}

window.hud-window--interactive {{
  background-color: {plate};
  border: 1px solid {_rgba(t.border, 0.55)};
  border-radius: {rad}px;
}}

box {{
  background-color: transparent;
}}

box.hud {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  min-width: 0;
  font-family: {t.font_body};
}}

box.hud.hud--interactive {{
  padding: 12px 14px;
  min-width: 280px;
}}

.hud-chip {{
  background-color: {chip};
  border: none;
  border-radius: {rad_sm}px;
  padding: 2px 7px;
  text-shadow:
    0 0 3px rgba(0, 0, 0, 0.9),
    0 1px 2px rgba(0, 0, 0, 0.85);
}}

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
  color: {t.title};
  font-family: {t.font_display};
  font-size: 13pt;
  font-weight: 700;
  letter-spacing: {t.letter_spacing_title};
}}

.section-title {{
  color: {t.section};
  font-family: {t.font_display};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.06em;
}}

.section-heading {{
  color: {t.accent};
  font-family: {t.font_display};
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: {section_tracking};
  text-transform: {section_transform};
}}

.section-title-btn {{
  background-color: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  color: {t.section};
  font-family: {t.font_display};
  font-size: 11pt;
  font-weight: 700;
  letter-spacing: 0.06em;
}}

.section-title-btn:hover {{
  color: {t.accent_soft};
  background-color: transparent;
}}

.section-title-btn:active {{
  color: {t.accent};
  background-color: transparent;
}}

.section-rule {{
  min-height: 1px;
  min-width: 160px;
  background-color: {_rgba(t.accent, 0.45)};
  margin: 2px 0 6px;
}}

.section-rule--heavy {{
  min-height: 3px;
  min-width: 200px;
  background-color: {_rgba(t.section, 0.7)};
  margin: 4px 0;
}}

.quest-timer {{
  font-family: {t.font_body};
  font-size: 10pt;
  font-weight: 700;
  font-feature-settings: "tnum";
}}

.quest-timer--green {{
  color: {t.ok};
}}

.quest-timer--orange {{
  color: {t.warn};
}}

.quest-timer--red {{
  color: {t.danger};
}}

.quest-timer--overdue {{
  color: {t.danger};
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}

button.hud-icon-btn {{
  color: {t.accent};
  font-family: {t.font_body};
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
  border-radius: {rad_btn}px;
  box-shadow: none;
  outline: none;
  opacity: 0.72;
}}

button.hud-icon-btn:hover {{
  color: {t.fg};
  background-color: {_rgba(t.accent, 0.18)};
  opacity: 1;
}}

button.hud-icon-btn:active {{
  color: {t.accent};
  background-color: {_rgba(t.accent, 0.28)};
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

.hud-settings-sep {{
  min-height: 1px;
  margin: 4px 0 2px;
  background-color: {_rgba(t.accent, 0.35)};
}}

.hud-settings-label {{
  color: {t.accent};
  font-family: {t.font_body};
  font-size: 9pt;
  font-weight: 600;
  letter-spacing: 0.04em;
}}

.hud-settings-section {{
  color: {t.fg};
  font-family: {t.font_display};
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: {section_transform};
  margin-top: 2px;
  opacity: 0.95;
}}

.hud-settings-hint {{
  font-size: 8pt;
  opacity: 0.75;
}}

.hud-opt-slider {{
  border: 1px solid {_rgba(t.border, 0.55)};
  border-radius: {rad_sm}px;
  overflow: hidden;
  background-color: {ink_soft};
}}

button.hud-opt {{
  color: {t.fg};
  font-family: {t.font_body};
  font-size: 9pt;
  font-weight: 500;
  letter-spacing: 0.02em;
  min-width: 0;
  min-height: 0;
  padding: 6px 10px;
  margin: 0;
  border: none;
  border-radius: 0;
  border-right: 1px solid {_rgba(t.border, 0.35)};
  background: none;
  background-color: transparent;
  box-shadow: none;
  outline: none;
}}

button.hud-opt--last {{
  border-right: none;
}}

button.hud-opt:hover {{
  color: {t.fg};
  background-color: {_rgba(t.accent, 0.14)};
}}

button.hud-opt--on {{
  color: {t.fg};
  background-color: {_rgba(t.accent, 0.28)};
  font-weight: 700;
}}

button.hud-opt--on:hover {{
  background-color: {_rgba(t.accent, 0.34)};
}}

.hud-settings-scale {{
  color: {t.fg};
  font-family: {t.font_body};
  font-size: 9pt;
  margin-top: 2px;
}}

.hud-settings-scale trough {{
  min-height: 6px;
  border-radius: 3px;
  background-color: {_rgba(t.accent, 0.18)};
}}

.hud-settings-scale highlight {{
  background-color: {_rgba(t.accent, 0.55)};
  border-radius: 3px;
}}

.hud-settings-scale slider {{
  min-width: 12px;
  min-height: 12px;
  border-radius: 6px;
  background-color: {t.accent};
  border: none;
  box-shadow: none;
}}

button.hud-drag {{
  color: {t.accent};
  font-family: {t.font_body};
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
  color: {t.accent};
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
  color: {t.fg};
  font-size: 11pt;
}}

.quest-progress {{
  color: {_rgba(t.fg, 0.92)};
  font-size: 9pt;
  font-feature-settings: "tnum";
}}

.hint {{
  color: {_rgba(t.fg_muted, 0.85)};
  font-size: 8pt;
}}

.notice-root {{
  background-color: rgba(0, 0, 0, 0);
}}

.major {{
  background-color: {_rgb_tuple(t.bg_rgb, 0.42)};
  border: none;
  border-radius: {rad}px;
  padding: 36px 48px 40px;
  font-family: {t.font_toast};
  text-shadow:
    0 0 4px rgba(0, 0, 0, 0.9),
    0 1px 3px rgba(0, 0, 0, 0.85);
}}

.major__eyebrow {{
  font-family: {t.font_toast};
  font-size: 22pt;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: {_rgba(t.section, 0.95)};
  margin-bottom: 0;
}}

.major__eyebrow-row {{
  margin-bottom: 12px;
}}

.major__significance--common {{
  color: {_rgba(t.sig_common, 0.95)};
}}

.major__significance--uncommon {{
  color: {_rgba(t.sig_uncommon, 0.98)};
}}

.major__significance--epic {{
  color: {_rgba(t.sig_epic, 0.98)};
}}

.major__significance--legendary {{
  color: {_rgba(t.sig_legendary, 0.98)};
}}

.major--quest_completed .major__eyebrow:not(.major__significance) {{
  color: {_rgba(t.ok, 0.95)};
}}

.major--quest_failed .major__eyebrow:not(.major__significance) {{
  color: {_rgba(t.danger, 0.95)};
}}

.major--quest_delayed .major__eyebrow:not(.major__significance) {{
  color: {_rgba(t.danger, 0.95)};
}}

.major--quest_started .major__eyebrow:not(.major__significance) {{
  color: {_rgba(t.section, 0.95)};
}}

.major__title {{
  font-family: {t.font_toast};
  font-size: 44pt;
  font-weight: 700;
  color: {t.fg};
}}

.major__rule {{
  min-height: 2px;
  background-color: {_rgba(t.fg, 0.45)};
  margin: 20px 0;
  border: none;
}}

.major__description {{
  font-size: 24pt;
  line-height: 1.45;
  color: {_rgba(t.fg, 0.88)};
}}

.major__detail {{
  font-size: 20pt;
  color: {_rgba(t.fg_muted, 0.9)};
  font-style: italic;
  margin-top: 12px;
}}

.minor {{
  min-width: 260px;
  padding: 12px 14px;
  border-radius: {rad_sm}px;
  border: 1px solid {_rgba(t.border, 0.55)};
  background-color: {_rgb_tuple(t.bg_rgb, 0.88)};
  font-family: {t.font_toast};
}}

.minor__title {{
  font-family: {t.font_toast};
  font-size: 11pt;
  font-weight: 700;
  color: {t.fg};
}}

.minor__change {{
  font-size: 9pt;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {_rgba(t.section, 0.9)};
  margin-top: 4px;
}}

.minor__detail {{
  font-size: 9pt;
  color: {_rgba(t.fg_muted, 0.9)};
  margin-top: 4px;
}}

.minor--step_completed .minor__change {{
  color: {_rgba(t.ok, 0.95)};
}}

.minor--quest_deleted .minor__change {{
  color: {_rgba(t.danger, 0.9)};
}}

.minor--quest_delayed .minor__change {{
  color: {_rgba(t.warn, 0.95)};
}}

.minor-log {{
  min-width: 0;
  max-width: none;
  padding: 8px 10px;
  font-family: {t.font_log};
}}

.minor-log__empty {{
  font-size: 9pt;
  color: {_rgba(t.fg_muted, 0.7)};
  font-style: italic;
}}

.minor-log__row {{
  padding: 1px 4px;
  margin: 0;
  border-radius: 0;
}}

.minor-log__ts {{
  font-size: 9pt;
  font-family: {t.font_log};
  color: {t.fg};
  letter-spacing: 0.02em;
}}

.minor-log__sep {{
  font-size: 9pt;
  color: {t.fg};
}}

.minor-log__title {{
  font-size: 9pt;
  font-weight: 700;
  color: {t.fg};
}}

.minor-log__title--common {{
  color: {_rgba(t.sig_common, 0.95)};
}}

.minor-log__title--uncommon {{
  color: {_rgba(t.sig_uncommon, 0.98)};
}}

.minor-log__title--epic {{
  color: {_rgba(t.sig_epic, 0.98)};
}}

.minor-log__title--legendary {{
  color: {_rgba(t.sig_legendary, 0.98)};
}}

.minor-log__msg {{
  font-size: 9pt;
  color: {_rgba(t.fg_muted, 0.9)};
}}

.minor-log__msg--step_completed,
.minor-log__msg--quest_completed {{
  color: {_rgba(t.ok, 0.95)};
}}

.minor-log__msg--quest_deleted,
.minor-log__msg--quest_failed {{
  color: {_rgba(t.danger, 0.9)};
}}

.minor-log__msg--quest_delayed {{
  color: {_rgba(t.warn, 0.95)};
}}

.minor-log__msg--pin_changed {{
  color: {_rgba(t.info, 0.95)};
}}

.minor-log__msg--status_changed {{
  color: {_rgba(t.sig_epic, 0.95)};
}}

.minor-log__msg--quest_created,
.minor-log__msg--quest_appeared {{
  color: {_rgba(t.section, 0.95)};
}}

.minor-log__msg--quest_updated {{
  color: {_rgba(t.fg_muted, 0.88)};
}}
"""


def export_pack_globals(theme: PackTheme) -> dict:
    """Values packs re-export as module-level constants."""
    return {
        "PACK_ID": theme.pack_id,
        "PACK_LABEL": theme.label,
        "FONT_DISPLAY": theme.font_display,
        "FONT_BODY": theme.font_body,
        "FONT_TOAST": theme.font_toast,
        "FONT_LOG": theme.font_log,
        "PASSTHROUGH_BG_RGB": theme.bg_rgb,
        "PASSTHROUGH_RADIUS": theme.radius,
        "AFK_SIG_RGB": {
            "common": theme.afk_common,
            "uncommon": theme.afk_uncommon,
            "epic": theme.afk_epic,
            "legendary": theme.afk_legendary,
        },
        "AFK_BORDER_RADIUS": theme.radius,
        "AFK_BORDER_WIDTH": 2,
        "AFK_BORDER_LEFT_WIDTH": 2,
        "MAJOR_FADE_IN_MS": theme.major_fade_in_ms,
        "MAJOR_FADE_OUT_MS": theme.major_fade_out_ms,
        "MAJOR_HOLD_MS": theme.major_hold_ms,
        "MINOR_FADE_IN_MS": theme.minor_fade_in_ms,
        "MINOR_FADE_OUT_MS": theme.minor_fade_out_ms,
        "MINOR_HOLD_MS": theme.minor_hold_ms,
    }
