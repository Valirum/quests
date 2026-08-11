#!/usr/bin/env bash
# Dual-run helper: Go API on :8766 (Python-era default for side-by-side).
# Prefer ./scripts/run-server.sh (:8765) for normal use.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export QUESTS_PORT="${QUESTS_PORT:-8766}"
exec "$ROOT/scripts/run-server.sh"
