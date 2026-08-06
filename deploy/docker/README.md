# Quests — Docker (сервер: api + bot + frontend)

HUD в Docker нет — на рабочей станции: `./scripts/run-overlay-smoke.sh` и
`quests-overlay.service`.

## Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| `api` | `8765` | FastAPI + собранный SPA + миграции при старте |
| `bot` | — | Telegram-бот → `http://api:8765`, прокси на хосте |
| `frontend` | `8080` | nginx → проксирует всё на `api` |

```bash
cd /path/to/Quests
cp -n .env.example .env
# QUESTS_TG_TOKEN, QUESTS_TG_USER_IDS; прокси на хосте :12334

docker compose -f deploy/docker/docker-compose.yml up -d --build

curl -sS http://127.0.0.1:8765/api/health
curl -sS http://127.0.0.1:8080/api/health
```

Логи: `docker compose -f deploy/docker/docker-compose.yml logs -f`

### Прокси для бота

По умолчанию `http://host.docker.internal:12334`. В `.env`:

```bash
QUESTS_TG_PROXY=http://host.docker.internal:7890
```

## HUD (не Docker)

```bash
export QUESTS_API=http://SERVER_IP:8765
./scripts/run-overlay-smoke.sh
# или: systemctl --user enable --now quests-overlay.service
```

## Данные

SQLite — volume `quests-data` (`/app/data`).

## Переменные

См. `.env.example`. В compose:

- `QUESTS_HOST=0.0.0.0`
- `QUESTS_API=http://api:8765` (бот)
- `QUESTS_RELOAD=0`
