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
| CLI | `uv run quests --help` | квесты + хуки; см. [`docs/cli.md`](docs/cli.md) |
| Оверлей | `./scripts/run-overlay-smoke.sh` | или `python -m overlay` |
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

User systemd units (не автозапуск из репо): [`deploy/systemd/`](deploy/systemd/).
