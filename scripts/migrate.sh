#!/usr/bin/env bash
# Apply DB migrations (or show current revision).
# Usage:
#   ./scripts/migrate.sh           # upgrade to head
#   ./scripts/migrate.sh current
#   ./scripts/migrate.sh stamp-head
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec uv run quests-migrate "$@"
