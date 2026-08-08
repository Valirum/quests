"""Ocean Drift — deep teal / seafoam HUD."""

from __future__ import annotations

from overlay.stylepacks._kit import PackTheme, build_modern_css

_SANS = '"IBM Plex Sans", "Noto Sans", "DejaVu Sans", sans-serif'
_MONO = '"IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace'
_SERIF = '"Source Serif 4", "Noto Serif", Georgia, serif'

_THEME = PackTheme(
    pack_id="ocean",
    label="Ocean Drift",
    font_display=_SANS,
    font_body=_SANS,
    font_toast=_SERIF,
    font_log=_MONO,
    bg_rgb=(10, 25, 30),
    radius=14,
    fg="#e8f4f2",
    fg_muted="#8fb8b0",
    fg_dim="#4a6e68",
    accent="#2ec4b6",
    accent_hot="#20a4a0",
    accent_soft="#7fdbda",
    title="#e8f4f2",
    section="#2ec4b6",
    border="#1a3a3c",
    ok="#6bcb77",
    warn="#ffd166",
    danger="#ef476f",
    info="#118ab2",
    sig_common="#8fb8b0",
    sig_uncommon="#6bcb77",
    sig_epic="#9b5de5",
    sig_legendary="#ffd166",
    afk_common=(143, 184, 176),
    afk_uncommon=(107, 203, 119),
    afk_epic=(155, 93, 229),
    afk_legendary=(255, 209, 102),
    letter_spacing_title="0.05em",
    uppercase_section=False,
    major_fade_in_ms=480,
    major_fade_out_ms=5000,
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
