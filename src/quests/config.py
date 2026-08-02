from __future__ import annotations

from pathlib import Path

# Project root: …/Quests
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "quests.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
# Sync URL for Alembic (and any sync tooling).
DATABASE_URL_SYNC = f"sqlite:///{DB_PATH}"

HOST = "127.0.0.1"
PORT = 8765
