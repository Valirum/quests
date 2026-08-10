#!/usr/bin/env bash
# Run the Go Quests API (dual-run: default port 8766 so Python can stay on 8765).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export QUESTS_ROOT="${QUESTS_ROOT:-$ROOT}"
export QUESTS_DATA_DIR="${QUESTS_DATA_DIR:-$ROOT/data}"
export QUESTS_HOST="${QUESTS_HOST:-127.0.0.1}"
export QUESTS_PORT="${QUESTS_PORT:-8766}"
cd "$ROOT/go"
exec go run ./cmd/quests-server
