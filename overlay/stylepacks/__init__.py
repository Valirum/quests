"""Style-pack loader for overlay (HUD + major/minor notices).

Swap packs: QUESTS_STYLE_PACK=fantasy|cyberpunk (restart overlay),
or apply_style_pack("cyberpunk") before CSS is loaded.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

DEFAULT_PACK = "fantasy"
_active = os.environ.get("QUESTS_STYLE_PACK", DEFAULT_PACK)


def active_pack() -> str:
    return _active


def apply_style_pack(name: str) -> None:
    global _active
    _active = name


def _load_pack(name: str | None = None) -> Any:
    pack = name or _active
    return importlib.import_module(f"overlay.stylepacks.{pack}")


def build_css(name: str | None = None) -> str:
    return _load_pack(name).build_css()


def pack_meta(name: str | None = None) -> dict:
    mod = _load_pack(name)
    return {
        "id": getattr(mod, "PACK_ID", name or _active),
        "label": getattr(mod, "PACK_LABEL", name or _active),
        "font_display": getattr(mod, "FONT_DISPLAY", "serif"),
        "font_body": getattr(mod, "FONT_BODY", "serif"),
    }
