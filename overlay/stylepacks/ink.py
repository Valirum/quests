"""Ink Mono — stark editorial black / paper white."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_SERIF = '"Literata", "Source Serif 4", "Noto Serif", "Liberation Serif", Georgia, serif'
_MONO = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace'
_SANS = '"IBM Plex Sans", "Noto Sans", sans-serif'

_THEME = PackTheme(
    pack_id="ink",
    label="Ink Mono",
    font_display=_SERIF,
    font_body=_MONO,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(12, 12, 12),
    radius=0,
    fg="#f5f5f0",
    fg_muted="#b0b0a8",
    fg_dim="#6a6a64",
    accent="#f5f5f0",
    accent_hot="#d0d0c8",
    accent_soft="#ffffff",
    title="#ffffff",
    section="#f5f5f0",
    border="#3a3a38",
    ok="#7dce82",
    warn="#e6c35c",
    danger="#e05a5a",
    info="#7aa2c8",
    sig_common="#b0b0a8",
    sig_uncommon="#7dce82",
    sig_epic="#9b8ec8",
    sig_legendary="#e6c35c",
    afk_common=(176, 176, 168),
    afk_uncommon=(125, 206, 130),
    afk_epic=(155, 142, 200),
    afk_legendary=(230, 195, 92),
    letter_spacing_title="0.14em",
    uppercase_section=True,
    major_fade_in_ms=200,
    major_fade_out_ms=3600,
    major_hold_ms=1000,
    minor_hold_ms=2400,
)

PACK_ID = _THEME.pack_id
PACK_LABEL = _THEME.label
FONT_DISPLAY = _THEME.font_display
FONT_BODY = _THEME.font_body
FONT_TOAST = _THEME.font_toast
FONT_LOG = _THEME.font_log
PASSTHROUGH_BG_RGB = _THEME.bg_rgb
PASSTHROUGH_RADIUS = _THEME.radius
AFK_SIG_RGB = {
    "common": _THEME.afk_common,
    "uncommon": _THEME.afk_uncommon,
    "epic": _THEME.afk_epic,
    "legendary": _THEME.afk_legendary,
}
AFK_BORDER_RADIUS = 0
AFK_BORDER_WIDTH = 1
AFK_BORDER_LEFT_WIDTH = 4
MAJOR_FADE_IN_MS = _THEME.major_fade_in_ms
MAJOR_FADE_OUT_MS = _THEME.major_fade_out_ms
MAJOR_HOLD_MS = _THEME.major_hold_ms
MINOR_FADE_IN_MS = _THEME.minor_fade_in_ms
MINOR_FADE_OUT_MS = _THEME.minor_fade_out_ms
MINOR_HOLD_MS = _THEME.minor_hold_ms


def build_css() -> str:
    return build_modern_css(_THEME)
