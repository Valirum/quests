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

### CI / GHCR (ветка `main`)

GitHub Actions (`.github/workflows/main.yml`) только собирает и пушит образы
(без SSH-деплоя):

1. `pytest` на push/PR
2. Path-filter: отдельно `quests-api` (api + frontend SPA) и `quests-bot`
3. Push в `ghcr.io/<owner>/quests-api:main` / `quests-bot:main` (BuildKit cache `type=gha`)

На сервере в `.env`:

```bash
QUESTS_API_IMAGE=ghcr.io/<owner>/quests-api:main
QUESTS_BOT_IMAGE=ghcr.io/<owner>/quests-bot:main
```

Один раз: `echo $CR_PAT | docker login ghcr.io -u USER --password-stdin`
(пакеты GitHub часто private — нужен PAT с `read:packages`).

Обновление контейнеров — вручную (`compose pull && up -d`) или Watchtower,
который сам подтягивает новый `:main`:

```bash
docker run -d --name watchtower --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$HOME/.docker/config.json:/config.json:ro" \
  containrrr/watchtower \
  --interval 60 quests-api quests-bot
```

(`config.json` после `docker login ghcr.io`; имена — `container_name` из compose.)

Ручной прогон сборки: Actions → **main** → Run workflow (`force_api` / `force_bot`).

Локально по-прежнему: без `QUESTS_*_IMAGE` → `quests-*:local` и `up --build`.

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
- `QUESTS_API` у бота: `http://127.0.0.1:8765` (host network)
- `QUESTS_RELOAD=0`
- `QUESTS_API_IMAGE` / `QUESTS_BOT_IMAGE` — опционально GHCR
