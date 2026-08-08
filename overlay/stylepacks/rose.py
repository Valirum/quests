"""Rose Pine — soft dusk pinks and muted mauve."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_SANS = '"IBM Plex Sans", "Noto Sans", "DejaVu Sans", sans-serif'
_MONO = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace'
_SERIF = '"Literata", "Source Serif 4", "Noto Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="rose",
    label="Rose Pine",
    font_display=_SERIF,
    font_body=_SANS,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(25, 23, 36),  # base
    radius=12,
    fg="#e0def4",
    fg_muted="#908caa",
    fg_dim="#6e6a86",
    accent="#ebbcba",
    accent_hot="#c4a7e7",
    accent_soft="#f6c177",
    title="#e0def4",
    section="#c4a7e7",
    border="#26233a",
    ok="#9ccfd8",
    warn="#f6c177",
    danger="#eb6f92",
    info="#31748f",
    sig_common="#908caa",
    sig_uncommon="#9ccfd8",
    sig_epic="#c4a7e7",
    sig_legendary="#f6c177",
    afk_common=(144, 140, 170),
    afk_uncommon=(156, 207, 216),
    afk_epic=(196, 167, 231),
    afk_legendary=(246, 193, 119),
    letter_spacing_title="0.03em",
    uppercase_section=False,
    major_fade_in_ms=560,
    major_hold_ms=1400,
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
