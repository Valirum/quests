# Quests — Docker

## Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| `api` | `8765` | FastAPI + собранный SPA + миграции при старте |
| `bot` | — | Telegram-бот → `http://api:8765`, прокси на хосте |
| `frontend` | `8080` | nginx → проксирует всё на `api` (удобный вход) |
| `overlay` | host | Wayland HUD, профиль `hud` (экспериментально) |

## Быстрый старт

```bash
cd /path/to/Quests
cp -n .env.example .env
# В .env: QUESTS_TG_TOKEN, QUESTS_TG_USER_IDS
# Прокси Telegram на хосте: http://127.0.0.1:12334

docker compose -f deploy/docker/docker-compose.yml up -d --build

curl -sS http://127.0.0.1:8765/api/health
# или через nginx:
curl -sS http://127.0.0.1:8080/api/health
```

Логи: `docker compose -f deploy/docker/docker-compose.yml logs -f`

## Прокси для бота

По умолчанию бот ходит на `http://host.docker.internal:12334`.
Подними HTTP-прокси на хосте на `:12334` или задай в `.env`:

```bash
QUESTS_TG_PROXY=http://host.docker.internal:7890
```

## HUD (overlay)

Только на машине с Wayland (niri и т.п.), **не** на headless-сервере:

```bash
export XDG_RUNTIME_DIR XDG_RUNTIME_DIR
export WAYLAND_DISPLAY
docker compose -f deploy/docker/docker-compose.yml --profile hud up -d --build overlay
```

Надёжнее по-прежнему запускать оверлей на хосте (`./scripts/run-overlay-smoke.sh`)
с `QUESTS_API=http://127.0.0.1:8765`.

## Данные

SQLite и файлы бота — volume `quests-data` (`/app/data` в контейнерах).

## Переменные

См. `.env.example`. В compose принудительно:

- `QUESTS_HOST=0.0.0.0`
- `QUESTS_API=http://api:8765` (бот)
- `QUESTS_RELOAD=0`
