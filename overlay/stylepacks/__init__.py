"""Style-pack loader for overlay (HUD + major/minor notices).

Swap packs: QUESTS_STYLE_PACK=<id>, overlay.json, or apply_style_pack().
Built-ins: fantasy, cyberpunk, gruvbox, nord, rose, ember, ink, ocean.
CSS hot-reload: reload_pack_module + CssProvider.load_from_string.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

DEFAULT_PACK = "fantasy"
_active = DEFAULT_PACK


def list_pack_ids() -> list[str]:
    """Discover style pack modules next to this package."""
    import overlay.stylepacks as pkg

    ids: list[str] = []
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.startswith("_"):
            continue
        ids.append(mod.name)
    return sorted(ids)


def list_packs() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for pack_id in list_pack_ids():
        try:
            meta = pack_meta(pack_id)
        except Exception:
            meta = {"id": pack_id, "label": pack_id}
        out.append({"id": str(meta["id"]), "label": str(meta["label"])})
    return out


def active_pack() -> str:
    return _active


def apply_style_pack(name: str, *, reload: bool = True) -> str:
    """Set active pack. Optionally reimport module (picks up CSS edits)."""
    global _active
    pack_id = (name or "").strip() or DEFAULT_PACK
    known = set(list_pack_ids())
    if pack_id not in known:
        pack_id = DEFAULT_PACK if DEFAULT_PACK in known else next(iter(known), DEFAULT_PACK)
    _active = pack_id
    if reload:
        reload_pack_module(pack_id)
    return _active


def reload_pack_module(name: str | None = None) -> Any:
    pack = name or _active
    mod = importlib.import_module(f"overlay.stylepacks.{pack}")
    return importlib.reload(mod)


def _load_pack(name: str | None = None) -> Any:
    pack = name or _active
    return importlib.import_module(f"overlay.stylepacks.{pack}")


def build_css(name: str | None = None) -> str:
    return _load_pack(name).build_css()


def pack_meta(name: str | None = None) -> dict:
    mod = _load_pack(name)
    rgb = getattr(mod, "PASSTHROUGH_BG_RGB", (26, 21, 16))
    try:
        r, g, b = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except (TypeError, ValueError, IndexError):
        r, g, b = 26, 21, 16
    return {
        "id": getattr(mod, "PACK_ID", name or _active),
        "label": getattr(mod, "PACK_LABEL", name or _active),
        "font_display": getattr(mod, "FONT_DISPLAY", "serif"),
        "font_body": getattr(mod, "FONT_BODY", "serif"),
        "passthrough_bg_rgb": (r, g, b),
        "passthrough_radius": int(getattr(mod, "PASSTHROUGH_RADIUS", 8)),
    }


def build_passthrough_css(
    *,
    mode: str = "chips",
    alpha: float = 0.6,
    text_alpha: float = 0.92,
    name: str | None = None,
) -> str:
    """Override CSS for HUD: passthrough bg + overall text/content opacity."""
    meta = pack_meta(name)
    r, g, b = meta["passthrough_bg_rgb"]
    radius = int(meta.get("passthrough_radius") or 8)
    a = max(0.0, min(1.0, float(alpha)))
    ta = max(0.0, min(1.0, float(text_alpha)))
    mode_key = "full" if str(mode).strip().lower() in {"full", "panel", "solid"} else "chips"
    text = f"""
.hud {{
  opacity: {ta:.3f};
}}
"""
    if mode_key == "full":
        border_a = min(1.0, a + 0.12)
        return text + f"""
window.hud-window--passthrough {{
  background-color: rgba({r}, {g}, {b}, {a:.3f});
  border: 1px solid rgba({r}, {g}, {b}, {border_a:.3f});
  border-radius: {radius}px;
}}
.hud:not(.hud--interactive) {{
  padding: 12px 14px;
  min-width: 280px;
}}
.hud:not(.hud--interactive) .hud-chip {{
  background-color: transparent;
  background-image: none;
  border-radius: 0;
  padding: 0;
}}
"""
    # Per-row bars on the inner plate only (see _hud_row) — never on a
    # full-width vertical-box child, or short lines become long ghost strips.
    return text + f"""
window.hud-window--passthrough {{
  background-color: transparent;
  border: none;
  border-radius: 0;
}}
.hud:not(.hud--interactive) {{
  background-color: transparent;
  padding: 0;
  min-width: 0;
}}
.hud:not(.hud--interactive) .hud-chip {{
  background-color: transparent;
  background-image: none;
  border-radius: 0;
  padding: 0;
}}
.hud:not(.hud--interactive) .hud-row {{
  background-color: rgba({r}, {g}, {b}, {a:.3f});
  background-image: none;
  border-radius: 0;
  padding: 2px 8px;
  min-width: 0;
  min-height: 0;
}}
window.hud-window--passthrough .section-rule,
window.hud-window--passthrough .section-rule--heavy,
.hud:not(.hud--interactive) .section-rule,
.hud:not(.hud--interactive) .section-rule--heavy {{
  opacity: 0;
  min-height: 0;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  background-color: transparent;
  background-image: none;
  box-shadow: none;
}}
.hud:not(.hud--interactive) .hud-section,
.hud:not(.hud--interactive) .hud-header {{
  background-color: transparent;
  background-image: none;
  min-width: 0;
  padding: 0;
  margin: 0;
  border: none;
}}
"""


def build_minor_log_css(
    *,
    mode: str = "full",
    bg_alpha: float = 0.72,
    text_alpha: float = 0.92,
    width: int = 520,
    height: int = 280,
    name: str | None = None,
) -> str:
    """Override CSS for the persistent minor event-log panel."""
    meta = pack_meta(name)
    r, g, b = meta["passthrough_bg_rgb"]
    radius = int(meta.get("passthrough_radius") or 8)
    ba = max(0.0, min(1.0, float(bg_alpha)))
    ta = max(0.0, min(1.0, float(text_alpha)))
    w = max(280, min(1200, int(width)))
    h = max(100, min(1200, int(height)))
    mode_key = "full" if str(mode).strip().lower() in {"full", "panel", "solid"} else "chips"
    border_a = min(1.0, ba + 0.14)

    if mode_key == "full":
        panel_bg = f"rgba({r}, {g}, {b}, {ba:.3f})"
        row_bg = "transparent"
        win_border = f"1px solid rgba({r}, {g}, {b}, {border_a:.3f})"
        win_radius = f"{radius}px"
    else:
        panel_bg = "transparent"
        row_bg = f"rgba({r}, {g}, {b}, {ba:.3f})"
        win_border = "none"
        win_radius = "0"

    return f"""
window.minor-log-window {{
  background-color: {panel_bg};
  border: {win_border};
  border-radius: {win_radius};
  min-width: {w}px;
  min-height: {h}px;
}}
.minor-log {{
  opacity: {ta:.3f};
  min-width: {w}px;
  min-height: {h}px;
  max-height: {h}px;
  overflow: hidden;
}}
.minor-log__row {{
  background-color: {row_bg};
  background-image: none;
}}
"""
