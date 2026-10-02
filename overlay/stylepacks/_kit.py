"""Shared modern HUD/toast CSS builder for palette-driven style packs."""

from __future__ import annotations

from dataclasses import dataclass

from overlay.stylepacks._css import render_css


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
    # Geometry. Defaults are the historical modern pack, so existing themes
    # keep their size. A pack overrides these instead of forking the CSS.
    hud_pad_y: int = 12
    hud_pad_x: int = 14
    hud_min_width: int = 280
    title_pt: int = 13
    section_pt: int = 11
    heading_pt: int = 10
    quest_pt: int = 11
    progress_pt: int = 9
    major_title_pt: int = 44
    major_eyebrow_pt: int = 22
    major_pad_y: int = 36
    major_pad_x: int = 48
    major_pad_bottom: int = 40
    major_desc_pt: int = 24
    major_tracking: str = "0.18em"
    chip_text_shadow: bool = True
    # bar = 1px + heavy 3px, hairline = 1px, none = hidden
    section_rule: str = "bar"
    # What the HUD and the major toast include. Defaults keep the gaming look.
    show_significance: bool = True
    show_major_body: bool = True
    show_step_progress: bool = True
    afk_glow: bool = True
    # Quest names only. Empty keeps font_display on those labels.
    font_quest: str = ""
    # Step lines. Empty keeps fg, so other packs stay as they are.
    step: str = ""


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
    toast_transform = section_transform
    hud_pad = f"{int(t.hud_pad_y)}px {int(t.hud_pad_x)}px"
    hud_min = int(t.hud_min_width)
    major_pad = f"{int(t.major_pad_y)}px {int(t.major_pad_x)}px {int(t.major_pad_bottom)}px"
    chip_shadow = (
        "text-shadow:\n    0 0 3px rgba(0, 0, 0, 0.9),\n    0 1px 2px rgba(0, 0, 0, 0.85);"
        if t.chip_text_shadow
        else "text-shadow: none;"
    )
    major_shadow = (
        "text-shadow:\n    0 0 4px rgba(0, 0, 0, 0.9),\n    0 1px 3px rgba(0, 0, 0, 0.85);"
        if t.chip_text_shadow
        else "text-shadow: none;"
    )
    rule = (t.section_rule or "bar").strip().lower()
    if rule == "none":
        rule_h, rule_w, rule_heavy_h, rule_heavy_w, rule_margin = 0, 0, 0, 0, "0"
    elif rule == "hairline":
        rule_h, rule_w, rule_heavy_h, rule_heavy_w, rule_margin = 1, 120, 1, 120, "2px 0 4px"
    else:
        rule_h, rule_w, rule_heavy_h, rule_heavy_w, rule_margin = 1, 160, 3, 200, "2px 0 6px"
    quest_font = t.font_quest or t.font_display
    step_color = t.step or t.fg
    flat_type = ""
    if not t.chip_text_shadow:
        flat_type = """
.hud label,
.hud button,
.hud .title,
.hud .section-title,
.hud .section-heading,
.hud .quest-title,
.hud .quest-progress {
  text-shadow: none;
}
"""

    return render_css("_kit.css", {**globals(), **locals()})


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
        "SHOW_SIGNIFICANCE": theme.show_significance,
        "SHOW_MAJOR_BODY": theme.show_major_body,
        "SHOW_STEP_PROGRESS": theme.show_step_progress,
        "AFK_GLOW": theme.afk_glow,
        "MAJOR_PAD_X": int(theme.major_pad_x),
        "SECTION_RULE": theme.section_rule,
        "HUD_PAD_Y": int(theme.hud_pad_y),
        "HUD_PAD_X": int(theme.hud_pad_x),
        "HUD_MIN_WIDTH": int(theme.hud_min_width),
    }
