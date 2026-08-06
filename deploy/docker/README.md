# Quests — Docker (сервер: api + bot + frontend)

HUD в Docker нет — на рабочей станции: `./scripts/run-overlay-smoke.sh` и
`quests-overlay.service`.

## Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| `api` | `8765` | FastAPI + собранный SPA + миграции при старте |
| `bot` | host net | Telegram-бот → `127.0.0.1:8765`, прокси `127.0.0.1:12334` |
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

Бот в `network_mode: host`, чтобы достучаться до прокси на `127.0.0.1`
(типичный sing-box / clash). Дефолт: `http://127.0.0.1:12334`.

Если прокси слушает только loopback — **не** используй `host.docker.internal`:
из контейнера в bridge-сети пакет приходит на docker0, а не на `127.0.0.1` →
connection refused.

Альтернатива без host-network: слушать прокси на `0.0.0.0:12334` и
`QUESTS_TG_PROXY=http://host.docker.internal:12334` (убери `network_mode: host`,
верни `QUESTS_API=http://api:8765`).

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
