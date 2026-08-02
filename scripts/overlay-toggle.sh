#!/usr/bin/env bash
# Toggle HUD click-through ↔ interactive (for niri Mod+Space etc.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 -m overlay toggle
