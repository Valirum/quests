"""Pytest bootstrap: isolate DB and silence background writers before app import."""

from __future__ import annotations

import os
import tempfile

# Must run at conftest import time (before test modules import quests.main / db).
os.environ.setdefault("QUESTS_MAINTENANCE", "0")
if "QUESTS_DATA_DIR" not in os.environ:
    os.environ["QUESTS_DATA_DIR"] = tempfile.mkdtemp(prefix="quests-test-")
