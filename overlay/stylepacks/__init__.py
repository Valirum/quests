"""Style-pack loader for overlay (HUD + major/minor notices).

Swap packs: QUESTS_STYLE_PACK=fantasy|cyberpunk, overlay.json, or apply_style_pack().
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
    name: str | None = None,
) -> str:
    """Override CSS for non-interactive HUD (full panel vs per-row bars)."""
    meta = pack_meta(name)
    r, g, b = meta["passthrough_bg_rgb"]
    radius = int(meta.get("passthrough_radius") or 8)
    a = max(0.0, min(1.0, float(alpha)))
    mode_key = "full" if str(mode).strip().lower() in {"full", "panel", "solid"} else "chips"
    if mode_key == "full":
        border_a = min(1.0, a + 0.12)
        return f"""
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
    # Per-row bars: each .hud-row hugs its content width.
    # Chips stay transparent so gaps inside a row are covered by the row bg.
    return f"""
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
}}
.hud:not(.hud--interactive) .section-rule {{
  opacity: 0;
  min-height: 0;
  margin: 0;
  padding: 0;
}}
"""
