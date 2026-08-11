#!/usr/bin/env bash
# Quests API (Go). Default :8765. Build binary if missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export QUESTS_ROOT="${QUESTS_ROOT:-$ROOT}"
export QUESTS_DATA_DIR="${QUESTS_DATA_DIR:-$ROOT/data}"
export QUESTS_HOST="${QUESTS_HOST:-127.0.0.1}"
export QUESTS_PORT="${QUESTS_PORT:-8765}"
BIN="${QUESTS_SERVER_BIN:-$ROOT/go/bin/quests-server}"
if [[ ! -x "$BIN" ]]; then
  echo "quests-server: binary missing, building…" >&2
  "$ROOT/scripts/build-server.sh"
fi
exec "$BIN"
