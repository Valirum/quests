#!/usr/bin/env bash
# Full bootstrap: uv sync + frontend deps + data dir.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/"
  exit 1
fi

echo "==> syncing Python deps (uv)"
uv sync --group dev

if command -v npm >/dev/null 2>&1; then
  echo "==> installing frontend deps (npm)"
  (cd frontend && npm install)
else
  echo "!! npm not found — skip frontend"
fi

mkdir -p data
echo "==> database migrations"
uv run quests-migrate upgrade

echo "==> ready"
echo "    API:      ./scripts/run-server.sh     → http://127.0.0.1:8765"
echo "    Frontend: ./scripts/run-frontend.sh   → http://127.0.0.1:5173 (dev, proxy /api)"
echo "    Build SPA: ./scripts/build-frontend.sh"
echo "    Migrate:  ./scripts/migrate.sh"
echo "    Overlay:  ./scripts/run-overlay-smoke.sh"
