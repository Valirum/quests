#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/amarant/Documents/projects/Quests
pkill -f 'cmd/quests-server' 2>/dev/null || true
sleep 0.3
TMP=$(mktemp -d /tmp/quests-go-XXXXXX)
cp "$ROOT/data/quests.db" "$TMP/"
export QUESTS_DATA_DIR="$TMP" QUESTS_PORT=8766 QUESTS_HOST=127.0.0.1 QUESTS_MAINTENANCE=0 QUESTS_ROOT="$ROOT"
cd "$ROOT/go"
go run ./cmd/quests-server >"$TMP/srv.log" 2>&1 &
SPID=$!
cleanup() { kill "$SPID" 2>/dev/null || true; }
trap cleanup EXIT
echo "TMP=$TMP pid=$SPID"
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8766/api/health >/dev/null; then break; fi
  sleep 0.3
done
BASE=http://127.0.0.1:8766
curl -sf "$BASE/api/health" >/dev/null
echo health_ok

QL=$(curl -sf -X POST "$BASE/api/questlines" -H 'Content-Type: application/json' -d '{"title":"go-parity-test","description":"tmp","color":"#112233"}')
QLID=$(echo "$QL" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
printf '\x89PNG\r\n\x1a\n' > /tmp/tiny.png
curl -sf -X POST "$BASE/api/questlines/$QLID/icon" -F "file=@/tmp/tiny.png;type=image/png" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("icon", d["custom_icon"])'
curl -sf -o /tmp/icon.out -w "icon_get:%{http_code}\n" "$BASE/api/questlines/$QLID/icon"
curl -sf -X DELETE "$BASE/api/questlines/$QLID/icon" >/dev/null
curl -sf -o /dev/null -w "ql_del:%{http_code}\n" -X DELETE "$BASE/api/questlines/$QLID"

T=$(curl -sf -X POST "$BASE/api/templates" -H 'Content-Type: application/json' -d '{"title":"go-tmpl","enabled":false,"freq":"daily","significance":"common"}')
TID=$(echo "$T" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -sf -X PATCH "$BASE/api/templates/$TID" -H 'Content-Type: application/json' -d '{"title":"go-tmpl-2"}' | python3 -c 'import sys,json; print("tmpl", json.load(sys.stdin)["title"])'
C=$(curl -sf -X POST "$BASE/api/templates/$TID/copy")
CID=$(echo "$C" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "copy_id=$CID"
curl -sf -o /dev/null -w "tmpl_del:%{http_code}\n" -X DELETE "$BASE/api/templates/$TID"
curl -sf -o /dev/null -w "tmpl_copy_del:%{http_code}\n" -X DELETE "$BASE/api/templates/$CID"

curl -sf "$BASE/api/hero" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("hero", d["xp"], d["momentum"], len(d["attributes"]))'
curl -sf "$BASE/api/stats?days=7" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("stats", d["range"]["from"], len(d["daily"]))'
curl -sf "$BASE/api/quest-log?limit=2" | python3 -c 'import sys,json; print("log", len(json.load(sys.stdin)))'
curl -sf "$BASE/api/context?questline=3" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("ctx", d["focus"], len(d["quests"]))'
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/" || true)
echo "spa:$code"

Q=$(curl -sf -X POST "$BASE/api/quests" -H 'Content-Type: application/json' -d '{"title":"reward-smoke","status":"active","significance":"common"}')
QID=$(echo "$Q" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
curl -sf -X PATCH "$BASE/api/quests/$QID" -H 'Content-Type: application/json' -d '{"status":"completed"}' >/dev/null
curl -sf "$BASE/api/hero" | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d["recent"][0]["reason"] if d.get("recent") else None; print("after", d["xp"], d["momentum"], r)'
echo ALL_OK
