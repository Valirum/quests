"""Nord Frost — cool arctic blue HUD."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_SANS = '"IBM Plex Sans", "Noto Sans", "DejaVu Sans", sans-serif'
_MONO = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace'
_SERIF = '"Noto Serif", "Liberation Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="nord",
    label="Nord Frost",
    font_display=_SANS,
    font_body=_SANS,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(46, 52, 64),  # nord0
    radius=10,
    fg="#eceff4",
    fg_muted="#d8dee9",
    fg_dim="#4c566a",
    accent="#88c0d0",
    accent_hot="#81a1c1",
    accent_soft="#e5e9f0",
    title="#eceff4",
    section="#8fbcbb",
    border="#4c566a",
    ok="#a3be8c",
    warn="#ebcb8b",
    danger="#bf616a",
    info="#5e81ac",
    sig_common="#d8dee9",
    sig_uncommon="#a3be8c",
    sig_epic="#b48ead",
    sig_legendary="#ebcb8b",
    afk_common=(216, 222, 233),
    afk_uncommon=(163, 190, 140),
    afk_epic=(180, 142, 173),
    afk_legendary=(235, 203, 139),
    letter_spacing_title="0.06em",
    uppercase_section=True,
    major_fade_in_ms=500,
    major_fade_out_ms=5200,
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
AFK_BORDER_LEFT_WIDTH = 2
MAJOR_FADE_IN_MS = _THEME.major_fade_in_ms
MAJOR_FADE_OUT_MS = _THEME.major_fade_out_ms
MAJOR_HOLD_MS = _THEME.major_hold_ms
MINOR_FADE_IN_MS = _THEME.minor_fade_in_ms
MINOR_FADE_OUT_MS = _THEME.minor_fade_out_ms
MINOR_HOLD_MS = _THEME.minor_hold_ms


def build_css() -> str:
    return build_modern_css(_THEME)
