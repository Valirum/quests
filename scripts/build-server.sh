#!/usr/bin/env bash
# Build Quests API binary → go/bin/quests-server
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${QUESTS_SERVER_OUT:-$ROOT/go/bin/quests-server}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT/go"
echo "==> building $OUT"
go build -o "$OUT" ./cmd/quests-server
echo "    ok: $OUT"
