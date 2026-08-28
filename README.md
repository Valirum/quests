# Quests

Менеджер задач в духе игрового журнала: веб-UI, API и Wayland-оверлей (HUD + тосты) для niri / CachyOS.

Стек: **Go (API + CLI) · SQLite · Svelte (Vite) · Python (MCP / Telegram / Alembic / LLM) · GTK4 + gtk4-layer-shell**

## Требования

- Go ≥ 1.26 (сборка API/CLI)
- Python ≥ 3.12, [uv](https://docs.astral.sh/uv/) (миграции, MCP, Telegram, `llm-add`)
- Node.js / npm (фронт)
- Для оверлея: `gtk4`, `gtk4-layer-shell`, `python-gobject` (Wayland)

```bash
# Arch / CachyOS (оверлей)
sudo pacman -S gtk4 gtk4-layer-shell python-gobject
```

## Развёртывание

```bash
./scripts/bootstrap.sh
```

Подтянет Python-зависимости (`uv sync`), соберёт Go CLI/API, `npm install` во `frontend/`, создаст `data/` и накатит миграции.

## Запуск

| Что | Команда | URL / заметка |
|-----|---------|----------------|
| API + SPA | `./scripts/run-server.sh` | http://127.0.0.1:8765 (нужен собранный `frontend/dist`) |
| Сборка API | `./scripts/build-server.sh` | → `go/bin/quests-server` |
| Фронт (HMR) | `./scripts/run-frontend.sh` | http://127.0.0.1:5173 (нужен запущенный API) |
| Сборка SPA | `./scripts/build-frontend.sh` | в `frontend/dist` |
| Миграции | `./scripts/migrate.sh` | или `uv run quests-migrate` |
| CLI | `./scripts/quests` / `go/bin/quests` | см. [`docs/cli.md`](docs/cli.md) |
| Оверлей | `./scripts/run-overlay-smoke.sh` | или `python -m overlay` |
| Telegram | `./scripts/run-telegram.sh` | HTTP-клиент к API |
| Шаблоны | UI «Шаблоны» / `/api/templates` | daily/weekly → инстансы-квесты |

Оверлей (IPC):

```bash
python -m overlay toggle    # passthrough ↔ interactive
python -m overlay monitor   # следующий монитор
python -m overlay status
```

Тема / позиция HUD сохраняются в `data/overlay.json` (`style_pack`, `monitor_connector`, `margins`). Переключение стиля — в interactive-режиме (dropdown). Env `QUESTS_STYLE_PACK` перекрывает конфиг на старте.

```bash
QUESTS_STYLE_PACK=cyberpunk ./scripts/run-overlay-smoke.sh
```

Layer-shell namespaces (для `niri msg layers` / `layer-rule`): `quests-overlay` (HUD), `quests-major`, `quests-minor`.

```kdl
// ~/.config/niri/config.kdl — пример
layer-rule {
    match namespace="^quests-"
    // block-out-from "screencast"
}
```

SQLite: `data/quests.db`.

User systemd units: [`deploy/systemd/`](deploy/systemd/).  
Деплой на сервер после клона: [`deploy/SERVER.md`](deploy/SERVER.md).  
Docker (api / bot / frontend): [`deploy/docker/`](deploy/docker/).
