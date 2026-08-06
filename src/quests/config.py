from __future__ import annotations

import os
from pathlib import Path

# Project root: …/Quests
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "quests.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
# Sync URL for Alembic (and any sync tooling).
DATABASE_URL_SYNC = f"sqlite:///{DB_PATH}"

# Bind address. Use 0.0.0.0 (or a LAN IP) when the API must accept remote HUD/bot/web.
HOST = (os.environ.get("QUESTS_HOST") or "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("QUESTS_PORT") or "8765")

# Comma-separated CORS origins. Empty → Vite localhost defaults.
# Example remote: QUESTS_CORS_ORIGINS=https://quests.example.com,http://192.168.1.10:5173
_cors_raw = (os.environ.get("QUESTS_CORS_ORIGINS") or "").strip()
if _cors_raw:
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    CORS_ORIGINS = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
