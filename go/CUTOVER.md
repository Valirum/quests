# Go API cutover

Dual-run Go beside Python, then switch the default listener.

## Dual-run

- Python (current default): `scripts/run-server.sh` → `:8765`
- Go: `scripts/run-go-server.sh` → `:8766` (same `QUESTS_DATA_DIR` / `quests.db`)

Do not point both at the same DB with writes enabled for long — use Go on a copy for smoke:

```bash
TMP=$(mktemp -d)
cp data/quests.db "$TMP/"
QUESTS_DATA_DIR=$TMP QUESTS_MAINTENANCE=0 ./scripts/run-go-server.sh
```

## Parity checklist

| Area | Go |
|------|-----|
| health / categories / quests + steps CRUD | yes |
| sync / events / WS / focus-quest | yes |
| maintenance expire + materialize | yes (`QUESTS_MAINTENANCE=0` to disable) |
| questlines + icon upload | yes |
| templates CRUD + copy | yes |
| hero + ledger rewards on status | yes (subset of Python) |
| stats + quest-log | yes |
| context | yes |
| SPA `frontend/dist` | yes if built |

Still Python-only until later: Telegram, GTK overlay process, MCP, STT, OpenAPI docs UI.

## Cutover

1. Build SPA: `cd frontend && npm run build`
2. Stop Python on `:8765`
3. `QUESTS_PORT=8765 ./scripts/run-go-server.sh` (or systemd/unit equivalent)
4. Point overlay / CLI / MCP `QUESTS_API` (or base URL) at the same host:port
5. Keep Python tree for overlay/TG/MCP helpers; API core is Go

Rollback: restart Python on `:8765`.
