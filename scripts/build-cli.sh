#!/usr/bin/env bash
# Build Quests CLI binary → go/bin/quests
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${QUESTS_CLI_OUT:-$ROOT/go/bin/quests}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT/go"
echo "==> building $OUT"
go build -o "$OUT" ./cmd/quests
echo "    ok: $OUT"
echo "    run: $OUT --help"
echo "    or:  ./scripts/quests --help"
