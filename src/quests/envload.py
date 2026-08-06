"""Load project `.env` into process env (if present)."""

from __future__ import annotations

from pathlib import Path

from quests.config import ROOT

_LOADED = False


def load_dotenv_files(*, override: bool = False) -> Path | None:
    """Load ``ROOT/.env`` via python-dotenv. Returns path if loaded."""
    global _LOADED
    if _LOADED and not override:
        return None
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None

    path = ROOT / ".env"
    if not path.is_file():
        _LOADED = True
        return None
    load_dotenv(path, override=override)
    _LOADED = True
    return path
