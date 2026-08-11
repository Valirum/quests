"""Pytest bootstrap: isolate DB and silence background writers."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("QUESTS_MAINTENANCE", "0")
if "QUESTS_DATA_DIR" not in os.environ:
    os.environ["QUESTS_DATA_DIR"] = tempfile.mkdtemp(prefix="quests-test-")
