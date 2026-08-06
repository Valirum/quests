"""Persistent overlay HUD settings (style, monitor, position, passthrough look)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("QUESTS_DATA_DIR") or ROOT / "data")
CONFIG_PATH = Path(os.environ.get("QUESTS_OVERLAY_CONFIG") or DATA_DIR / "overlay.json")

DEFAULTS: dict[str, Any] = {
    "style_pack": "fantasy",
    "monitor_index": 0,
    "monitor_connector": "",
    "margin_top": 24,
    "margin_right": 24,
    # Passthrough (non-interactive) look only.
    "passthrough_bg_mode": "chips",  # chips | full
    "passthrough_bg_alpha": 0.6,
    # Toast lanes (major = fullscreen center, minor = small corner).
    "toasts_major": True,
    "toasts_minor": True,
    # HUD category lane (slug from /api/categories); empty → first available.
    "hud_category": "",
    # Optional Quests API base (overridden by QUESTS_API env).
    "api_base": "",
}


def _clamp_alpha(value: Any, default: float = 0.6) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"1", "true", "yes", "on", "вкл"}:
            return True
        if key in {"0", "false", "no", "off", "выкл"}:
            return False
    return default


def _normalize_bg_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"full", "panel", "solid"}:
        return "full"
    return "chips"


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            if "style_pack" in data and isinstance(data["style_pack"], str):
                cfg["style_pack"] = data["style_pack"].strip() or DEFAULTS["style_pack"]
            if "monitor_index" in data:
                try:
                    cfg["monitor_index"] = max(0, int(data["monitor_index"]))
                except (TypeError, ValueError):
                    pass
            if "monitor_connector" in data and isinstance(data["monitor_connector"], str):
                cfg["monitor_connector"] = data["monitor_connector"].strip()
            for key in ("margin_top", "margin_right"):
                if key in data:
                    try:
                        cfg[key] = max(0, int(data[key]))
                    except (TypeError, ValueError):
                        pass
            if "passthrough_bg_mode" in data:
                cfg["passthrough_bg_mode"] = _normalize_bg_mode(data["passthrough_bg_mode"])
            if "passthrough_bg_alpha" in data:
                cfg["passthrough_bg_alpha"] = _clamp_alpha(
                    data["passthrough_bg_alpha"], DEFAULTS["passthrough_bg_alpha"]
                )
            if "toasts_major" in data:
                cfg["toasts_major"] = _as_bool(data["toasts_major"], DEFAULTS["toasts_major"])
            if "toasts_minor" in data:
                cfg["toasts_minor"] = _as_bool(data["toasts_minor"], DEFAULTS["toasts_minor"])
            if "hud_category" in data and isinstance(data["hud_category"], str):
                cfg["hud_category"] = data["hud_category"].strip()
            if "api_base" in data and isinstance(data["api_base"], str):
                cfg["api_base"] = data["api_base"].strip().rstrip("/")
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    env_pack = (os.environ.get("QUESTS_STYLE_PACK") or "").strip()
    if env_pack:
        cfg["style_pack"] = env_pack
    return cfg


def save(cfg: dict[str, Any]) -> None:
    payload = {
        "style_pack": str(cfg.get("style_pack") or DEFAULTS["style_pack"]),
        "monitor_index": max(0, int(cfg.get("monitor_index") or 0)),
        "monitor_connector": str(cfg.get("monitor_connector") or ""),
        "margin_top": max(0, int(cfg.get("margin_top") or 0)),
        "margin_right": max(0, int(cfg.get("margin_right") or 0)),
        "passthrough_bg_mode": _normalize_bg_mode(cfg.get("passthrough_bg_mode")),
        "passthrough_bg_alpha": _clamp_alpha(
            cfg.get("passthrough_bg_alpha"), DEFAULTS["passthrough_bg_alpha"]
        ),
        "toasts_major": _as_bool(cfg.get("toasts_major"), DEFAULTS["toasts_major"]),
        "toasts_minor": _as_bool(cfg.get("toasts_minor"), DEFAULTS["toasts_minor"]),
        "hud_category": str(cfg.get("hud_category") or "").strip(),
        "api_base": str(cfg.get("api_base") or "").strip().rstrip("/"),
    }
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
