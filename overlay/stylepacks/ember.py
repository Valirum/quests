"""Ember Forge — hot coals, ember orange, forged iron."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_DISP = '"Oxanium", "Rajdhani", "Noto Sans Display", "Noto Sans", sans-serif'
_SANS = '"Noto Sans", "DejaVu Sans", sans-serif'
_MONO = '"JetBrainsMono Nerd Font", "JetBrains Mono", ui-monospace, monospace'
_SERIF = '"Noto Serif", "Liberation Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="ember",
    label="Ember Forge",
    font_display=_DISP,
    font_body=_SANS,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(22, 12, 10),
    radius=4,
    fg="#f4e8dc",
    fg_muted="#c4a090",
    fg_dim="#7a5548",
    accent="#ff6b35",
    accent_hot="#e85d04",
    accent_soft="#ffba08",
    title="#ffe8d6",
    section="#ff6b35",
    border="#5c2e1f",
    ok="#80b918",
    warn="#ffba08",
    danger="#d00000",
    info="#48cae4",
    sig_common="#c4a090",
    sig_uncommon="#80b918",
    sig_epic="#c77dff",
    sig_legendary="#ffba08",
    afk_common=(196, 160, 144),
    afk_uncommon=(128, 185, 24),
    afk_epic=(199, 125, 255),
    afk_legendary=(255, 186, 8),
    letter_spacing_title="0.1em",
    uppercase_section=True,
    major_fade_in_ms=300,
    major_fade_out_ms=4000,
    minor_fade_in_ms=160,
    minor_hold_ms=2600,
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
AFK_BORDER_RADIUS = _THEME.radius
AFK_BORDER_WIDTH = 2
AFK_BORDER_LEFT_WIDTH = 3
MAJOR_FADE_IN_MS = _THEME.major_fade_in_ms
MAJOR_FADE_OUT_MS = _THEME.major_fade_out_ms
MAJOR_HOLD_MS = _THEME.major_hold_ms
MINOR_FADE_IN_MS = _THEME.minor_fade_in_ms
MINOR_FADE_OUT_MS = _THEME.minor_fade_out_ms
MINOR_HOLD_MS = _THEME.minor_hold_ms


def build_css() -> str:
    return build_modern_css(_THEME)
