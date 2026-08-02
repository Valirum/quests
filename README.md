# Quests

Менеджер задач в духе игрового журнала: веб-UI, API и Wayland-оверлей (HUD + тосты) для niri / CachyOS.

Стек: **Python · FastAPI · SQLite · Svelte (Vite) · GTK4 + gtk4-layer-shell**

## Требования

- Python ≥ 3.12, [uv](https://docs.astral.sh/uv/)
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

Подтянет Python-зависимости (`uv sync`), `npm install` во `frontend/`, создаст `data/` и накатит миграции.

## Запуск

| Что | Команда | URL / заметка |
|-----|---------|----------------|
| API + SPA | `./scripts/run-server.sh` | http://127.0.0.1:8765 (нужен собранный `frontend/dist`) |
| Фронт (HMR) | `./scripts/run-frontend.sh` | http://127.0.0.1:5173 (нужен запущенный API) |
| Сборка SPA | `./scripts/build-frontend.sh` | в `frontend/dist` |
| Миграции | `./scripts/migrate.sh` | или `uv run quests-migrate` |
| Оверлей | `./scripts/run-overlay-smoke.sh` | или `python -m overlay` |

Оверлей (IPC):

```bash
python -m overlay toggle    # passthrough ↔ interactive
python -m overlay monitor   # следующий монитор
python -m overlay status
```

Тема оверлея: `QUESTS_STYLE_PACK=fantasy|cyberpunk` (по умолчанию `fantasy`).

```bash
QUESTS_STYLE_PACK=cyberpunk ./scripts/run-overlay-smoke.sh
```

SQLite: `data/quests.db`.
