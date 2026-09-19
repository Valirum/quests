#!/usr/bin/env bash
# Pull prod SQLite (+ icons) into ./data for local API poking.
#
#   ./scripts/pull-prod-data.sh
#   ./scripts/pull-prod-data.sh --start          # then ./scripts/dev-api-docker.sh
#   ./scripts/pull-prod-data.sh --pull-image     # also refresh quests-api:local from GHCR
#
# Needs: ssh to the prod host + docker on both sides.
# Volume path on the host is root-only — we tar from inside the API container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${QUESTS_DATA_DIR:-$ROOT/data}"
SSH_HOST="${QUESTS_PROD_SSH:-amarant@100.125.103.43}"
CONTAINER="${QUESTS_PROD_CONTAINER:-quests-api}"
IMAGE="${QUESTS_API_IMAGE:-ghcr.io/valirum/quests-api:main}"

START=0
PULL_IMAGE=0
for arg in "$@"; do
  case "$arg" in
    --start) START=1 ;;
    --pull-image) PULL_IMAGE=1 ;;
    -h|--help)
      cat <<EOF
usage: $0 [--pull-image] [--start]

  Pull /app/data from prod container \`$CONTAINER\` on \`$SSH_HOST\`
  into \`$DATA\` (bind-mounted by docker-compose.dev.yml).

env:
  QUESTS_PROD_SSH         default: amarant@100.125.103.43
  QUESTS_PROD_CONTAINER   default: quests-api
  QUESTS_DATA_DIR         default: <repo>/data
  QUESTS_API_IMAGE        default: ghcr.io/valirum/quests-api:main
EOF
      exit 0
      ;;
    *)
      echo "unknown arg: $arg (try --help)" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$DATA"

# Keep workstation overlay HUD config if present.
overlay_bak=""
if [[ -f "$DATA/overlay.json" ]]; then
  overlay_bak="$(mktemp)"
  cp -a "$DATA/overlay.json" "$overlay_bak"
fi

echo "pulling $SSH_HOST:$CONTAINER:/app/data → $DATA" >&2
ssh -o BatchMode=yes "$SSH_HOST" \
  "docker exec $CONTAINER tar czf - -C /app/data ." \
  | tar xzf - -C "$DATA"

if [[ -n "$overlay_bak" ]]; then
  mv -f "$overlay_bak" "$DATA/overlay.json"
fi

if [[ -f "$DATA/quests.db" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    notes="$(sqlite3 "$DATA/quests.db" 'SELECT COUNT(*) FROM note;' 2>/dev/null || echo '?')"
    quests="$(sqlite3 "$DATA/quests.db" 'SELECT COUNT(*) FROM quest;' 2>/dev/null || echo '?')"
    echo "ok: quests.db (notes=$notes quests=$quests)" >&2
  else
    ls -lh "$DATA/quests.db" >&2
  fi
else
  echo "error: quests.db missing after pull" >&2
  exit 1
fi

if [[ "$PULL_IMAGE" -eq 1 ]]; then
  echo "pulling $IMAGE → quests-api:local" >&2
  if docker pull "$IMAGE"; then
    docker tag "$IMAGE" quests-api:local
  else
    echo "ghcr pull failed — docker save|load from prod" >&2
    ssh -o BatchMode=yes "$SSH_HOST" "docker save $IMAGE" | docker load
    docker tag "$IMAGE" quests-api:local
  fi
fi

if [[ "$START" -eq 1 ]]; then
  exec "$ROOT/scripts/dev-api-docker.sh"
fi

echo "next: ./scripts/dev-api-docker.sh   # UI http://127.0.0.1:8765/" >&2
