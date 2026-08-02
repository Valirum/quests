#!/usr/bin/env bash
# Run Wayland overlay (HUD + center toasts).
set -euo pipefail

if ! pacman -Q gtk4-layer-shell &>/dev/null; then
  echo "Missing gtk4-layer-shell. Install with:"
  echo "  sudo pacman -S gtk4-layer-shell"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 -m overlay
