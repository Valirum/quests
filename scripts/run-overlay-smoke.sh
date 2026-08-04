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

# Optional vendored pywayland (ext-idle-notify for major toasts).
VENDOR="$ROOT/overlay/_vendor"
if [[ ! -d "$VENDOR/pywayland" ]]; then
  mkdir -p "$VENDOR"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --target "$VENDOR" pywayland >/dev/null 2>&1 || true
  else
    python3 -m pip install --target "$VENDOR" pywayland >/dev/null 2>&1 || true
  fi
fi
export PYTHONPATH="${VENDOR}${PYTHONPATH:+:$PYTHONPATH}"

exec python3 -m overlay
