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
    # HUD look (passthrough chips/full + text opacity).
    "passthrough_bg_mode": "chips",  # chips | full
    "passthrough_bg_alpha": 0.6,
    "hud_text_alpha": 0.92,
    # Major toasts on/off.
    "toasts_major": True,
    # Minor: off | toast | log (+ look when log).
    "toasts_minor_mode": "toast",
    "minor_bg_mode": "full",  # chips | full (выделение)
    "minor_bg_alpha": 0.72,
    "minor_text_alpha": 0.92,
    "minor_log_width": 520,
    "minor_log_height": 280,
    "minor_log_line_mode": "clip",  # clip | wrap
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
        return True if value else False
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


def _normalize_minor_mode(value: Any, *, legacy_bool: Any = None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"off", "toast", "log"}:
        return raw
    # Migrate old toasts_minor bool.
    if legacy_bool is not None:
        return "toast" if _as_bool(legacy_bool, True) else "off"
    return str(DEFAULTS["toasts_minor_mode"])


def _clamp_int(value: Any, default: int, *, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _normalize_line_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"wrap", "перенос", "word"}:
        return "wrap"
    return "clip"


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
            if "hud_text_alpha" in data:
                cfg["hud_text_alpha"] = _clamp_alpha(
                    data["hud_text_alpha"], DEFAULTS["hud_text_alpha"]
                )
            elif "hud_bg_alpha" in data:
                # Old interactive-bg slider → treat as text alpha fallback.
                cfg["hud_text_alpha"] = _clamp_alpha(
                    data["hud_bg_alpha"], DEFAULTS["hud_text_alpha"]
                )
            if "toasts_major" in data:
                cfg["toasts_major"] = _as_bool(data["toasts_major"], DEFAULTS["toasts_major"])
            if "toasts_minor_mode" in data or "toasts_minor" in data:
                cfg["toasts_minor_mode"] = _normalize_minor_mode(
                    data.get("toasts_minor_mode"),
                    legacy_bool=data.get("toasts_minor"),
                )
            if "minor_bg_mode" in data:
                cfg["minor_bg_mode"] = _normalize_bg_mode(data["minor_bg_mode"])
            if "minor_bg_alpha" in data:
                cfg["minor_bg_alpha"] = _clamp_alpha(
                    data["minor_bg_alpha"], DEFAULTS["minor_bg_alpha"]
                )
            if "minor_text_alpha" in data:
                cfg["minor_text_alpha"] = _clamp_alpha(
                    data["minor_text_alpha"], DEFAULTS["minor_text_alpha"]
                )
            if "minor_log_width" in data:
                cfg["minor_log_width"] = _clamp_int(
                    data["minor_log_width"], DEFAULTS["minor_log_width"], lo=280, hi=1200
                )
            if "minor_log_height" in data:
                cfg["minor_log_height"] = _clamp_int(
                    data["minor_log_height"], DEFAULTS["minor_log_height"], lo=100, hi=1200
                )
            if "minor_log_line_mode" in data:
                cfg["minor_log_line_mode"] = _normalize_line_mode(data["minor_log_line_mode"])
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
        "hud_text_alpha": _clamp_alpha(cfg.get("hud_text_alpha"), DEFAULTS["hud_text_alpha"]),
        "toasts_major": _as_bool(cfg.get("toasts_major"), DEFAULTS["toasts_major"]),
        "toasts_minor_mode": _normalize_minor_mode(cfg.get("toasts_minor_mode")),
        "minor_bg_mode": _normalize_bg_mode(cfg.get("minor_bg_mode")),
        "minor_bg_alpha": _clamp_alpha(
            cfg.get("minor_bg_alpha"), DEFAULTS["minor_bg_alpha"]
        ),
        "minor_text_alpha": _clamp_alpha(
            cfg.get("minor_text_alpha"), DEFAULTS["minor_text_alpha"]
        ),
        "minor_log_width": _clamp_int(
            cfg.get("minor_log_width"), DEFAULTS["minor_log_width"], lo=280, hi=1200
        ),
        "minor_log_height": _clamp_int(
            cfg.get("minor_log_height"), DEFAULTS["minor_log_height"], lo=100, hi=1200
        ),
        "minor_log_line_mode": _normalize_line_mode(cfg.get("minor_log_line_mode")),
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
