"""Quiet — small HUD, modest toast, no rarity word.

AFK still pulses: the blink is how an idle toast gets noticed. Quest names
are serif; the rest of the HUD is sans, without a glyph shadow.
"""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css, export_pack_globals

_SANS = '"IBM Plex Sans", "Noto Sans", sans-serif'
_SERIF = '"Literata", "Source Serif 4", "Noto Serif", "Liberation Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="quiet",
    label="Тихо",
    font_display=_SANS,
    font_body=_SANS,
    font_toast=_SANS,
    font_log=_SANS,
    font_quest=_SERIF,
    bg_rgb=(22, 22, 22),
    radius=4,
    fg="#d8d6d0",
    fg_muted="#8d8b84",
    fg_dim="#5c5b56",
    accent="#d8d6d0",
    accent_hot="#f2f0ea",
    accent_soft="#f2f0ea",
    title="#f2f0ea",
    section="#f2f0ea",
    step="#8a8882",
    border="#3a3936",
    ok="#9aaa8a",
    warn="#c4a36a",
    danger="#c47a72",
    info="#8aa0b0",
    sig_common="#8d8b84",
    sig_uncommon="#8d8b84",
    sig_epic="#8d8b84",
    sig_legendary="#8d8b84",
    afk_common=(236, 232, 220),
    afk_uncommon=(236, 232, 220),
    afk_epic=(236, 232, 220),
    afk_legendary=(236, 232, 220),
    letter_spacing_title="0",
    uppercase_section=False,
    major_fade_in_ms=160,
    major_fade_out_ms=280,
    major_hold_ms=900,
    minor_fade_in_ms=140,
    minor_fade_out_ms=220,
    minor_hold_ms=1600,
    hud_pad_y=8,
    hud_pad_x=10,
    hud_min_width=200,
    title_pt=12,
    section_pt=11,
    heading_pt=9,
    quest_pt=11,
    progress_pt=9,
    major_title_pt=21,
    major_eyebrow_pt=14,
    major_pad_y=16,
    major_pad_x=21,
    major_pad_bottom=18,
    major_desc_pt=16,
    major_tracking="0",
    chip_text_shadow=False,
    section_rule="none",
    show_significance=False,
    show_major_body=False,
    show_step_progress=True,
    afk_glow=True,
)

_EXPORTED = export_pack_globals(_THEME)
PACK_ID = _EXPORTED["PACK_ID"]
PACK_LABEL = _EXPORTED["PACK_LABEL"]
FONT_DISPLAY = _EXPORTED["FONT_DISPLAY"]
FONT_BODY = _EXPORTED["FONT_BODY"]
FONT_TOAST = _EXPORTED["FONT_TOAST"]
FONT_LOG = _EXPORTED["FONT_LOG"]
PASSTHROUGH_BG_RGB = _EXPORTED["PASSTHROUGH_BG_RGB"]
PASSTHROUGH_RADIUS = _EXPORTED["PASSTHROUGH_RADIUS"]
AFK_SIG_RGB = _EXPORTED["AFK_SIG_RGB"]
AFK_BORDER_RADIUS = _EXPORTED["AFK_BORDER_RADIUS"]
AFK_BORDER_WIDTH = 1
AFK_BORDER_LEFT_WIDTH = 1
MAJOR_FADE_IN_MS = _EXPORTED["MAJOR_FADE_IN_MS"]
MAJOR_FADE_OUT_MS = _EXPORTED["MAJOR_FADE_OUT_MS"]
MAJOR_HOLD_MS = _EXPORTED["MAJOR_HOLD_MS"]
MINOR_FADE_IN_MS = _EXPORTED["MINOR_FADE_IN_MS"]
MINOR_FADE_OUT_MS = _EXPORTED["MINOR_FADE_OUT_MS"]
MINOR_HOLD_MS = _EXPORTED["MINOR_HOLD_MS"]
SHOW_SIGNIFICANCE = _EXPORTED["SHOW_SIGNIFICANCE"]
SHOW_MAJOR_BODY = _EXPORTED["SHOW_MAJOR_BODY"]
SHOW_STEP_PROGRESS = _EXPORTED["SHOW_STEP_PROGRESS"]
AFK_GLOW = _EXPORTED["AFK_GLOW"]
MAJOR_PAD_X = _EXPORTED["MAJOR_PAD_X"]
SECTION_RULE = _EXPORTED["SECTION_RULE"]
HUD_PAD_Y = _EXPORTED["HUD_PAD_Y"]
HUD_PAD_X = _EXPORTED["HUD_PAD_X"]
HUD_MIN_WIDTH = _EXPORTED["HUD_MIN_WIDTH"]


def build_css() -> str:
    return build_modern_css(_THEME)
