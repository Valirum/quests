#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "No .venv — run ./scripts/bootstrap.sh first"
  exit 1
fi

exec uv run quests-telegram "$@"
