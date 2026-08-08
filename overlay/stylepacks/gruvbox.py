"""Gruvbox Green — modern pack matching the web journal theme."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_MONO = (
    '"IBM Plex Mono", "JetBrainsMono Nerd Font", "JetBrains Mono", '
    '"JetBrainsMono NF", ui-monospace, monospace'
)
_SANS = '"IBM Plex Sans", "Noto Sans", "DejaVu Sans", sans-serif'
_SERIF = '"Source Serif 4", "Literata", "Noto Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="gruvbox",
    label="Gruvbox Green",
    font_display=_SANS,
    font_body=_MONO,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(29, 32, 33),  # #1d2021
    radius=8,
    fg="#ebdbb2",
    fg_muted="#a89984",
    fg_dim="#928374",
    accent="#b8bb26",
    accent_hot="#98971a",
    accent_soft="#d5c4a1",
    title="#ebdbb2",
    section="#b8bb26",
    border="#504945",
    ok="#8ec07c",
    warn="#fe8019",
    danger="#fb4934",
    info="#83a598",
    sig_common="#a89984",
    sig_uncommon="#8ec07c",
    sig_epic="#83a598",
    sig_legendary="#fabd2f",
    afk_common=(168, 153, 132),
    afk_uncommon=(142, 192, 124),
    afk_epic=(131, 165, 152),
    afk_legendary=(250, 189, 47),
    letter_spacing_title="0.02em",
    uppercase_section=False,
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
