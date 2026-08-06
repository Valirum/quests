# Деплой Quests на сервер (после `git clone`)

Два пути: **Docker** (проще на VPS) или **systemd + uv** (как на рабочей станции).

Оверлей (HUD) на сервере **не** нужен — только API + SPA (+ опционально Telegram-бот).  
HUD остаётся на рабочей станции с Wayland и ходит на сервер через `QUESTS_API`.

---

## Вариант A — Docker (рекомендуется на сервере)

```bash
cd ~
git clone <repo-url> Quests
cd Quests
cp .env.example .env
$EDITOR .env   # QUESTS_TG_* ; прокси см. ниже

# HTTP-прокси для Telegram на хосте :12334 (свой стек), затем:
docker compose -f deploy/docker/docker-compose.yml up -d --build

curl -sS http://127.0.0.1:8765/api/health
# UI: http://SERVER_IP:8765  или  :8080 (nginx)
```

Подробнее: [`docker/README.md`](docker/README.md).

Дальше — firewall на `8765`/`8080`, на ПК HUD: `QUESTS_API=http://SERVER_IP:8765`.

---

## Вариант B — systemd (после клона без Docker)

Ниже путь клонирования: `~/Quests`. Если другой — правь `WorkingDirectory` / `ExecStart` в unit-файлах.

Локальная разработка в `~/Documents/projects/Quests`:

```bash
ln -sfn ~/Documents/projects/Quests ~/Quests
```

---

## 0. Зависимости на сервере

```bash
# uv: https://docs.astral.sh/uv/
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js / npm (сборка SPA)
# Arch: sudo pacman -S nodejs npm
# Debian/Ubuntu: sudo apt install nodejs npm
```

Для бота нужен исходящий доступ к Telegram **через HTTP-прокси**
(`QUESTS_TG_PROXY`, по умолчанию `http://127.0.0.1:12334`). Подними любой
локальный прокси на этом порту (или укажи свой URL в `.env`) до старта бота.

---

## 1. Клон и bootstrap

```bash
cd ~
git clone <repo-url> Quests
cd Quests

./scripts/bootstrap.sh
./scripts/build-frontend.sh
```

`bootstrap.sh`: `uv sync`, `npm install`, `data/`, миграции DB.  
`build-frontend.sh`: `frontend/dist` — отдаёт API на `:8765`.

---

## 2. Конфиг `.env`

```bash
cp .env.example .env
$EDITOR .env
```

Минимум для удалённого API:

```bash
# Слушать не только localhost
QUESTS_HOST=0.0.0.0
QUESTS_PORT=8765

# Telegram (если бот на этом же хосте)
QUESTS_TG_TOKEN=…
QUESTS_TG_USER_IDS=…          # через запятую
# QUESTS_TG_PROXY=http://127.0.0.1:12334

# API base для бота (локально можно не трогать)
# QUESTS_API=http://127.0.0.1:8765
```

CORS нужен только если Vite/SPA открывают с другого origin:

```bash
# QUESTS_CORS_ORIGINS=https://quests.example.com,http://LAN_IP:5173
```

Открой firewall / security group на TCP `8765` (или поставь nginx/caddy перед API).

---

## 3. Проверка руками

```bash
./scripts/run-server.sh
# в другом терминале:
curl -sS http://127.0.0.1:8765/api/health
# с другой машины:
curl -sS http://SERVER_IP:8765/api/health
```

Бот (после заполнения TG-переменных):

```bash
./scripts/run-telegram.sh
```

В веб-UI чипы **API / HUD / Bot**: Bot зелёный после heartbeat (~несколько секунд).

Остановка: `Ctrl+C`, дальше — systemd.

---

## 4. systemd (user units)

### 4.1. Пути в unit-файлах

В репо units рассчитаны на `%h/Quests` (т.е. `~/Quests`).  
Если клон в другом месте — поправь `WorkingDirectory` и `ExecStart` во всех `*.service`, либо сделай симлинк:

```bash
ln -sfn "$PWD" ~/Quests
```

Для локальной копии в `~/Documents/projects/Quests` — либо симлинк, либо правь пути обратно.

### 4.2. Установка units

```bash
cd ~/Quests

mkdir -p ~/.config/systemd/user
ln -sf "$PWD/deploy/systemd/user/"*.service ~/.config/systemd/user/

# user-сервисы без активной сессии (сервер / SSH):
sudo loginctl enable-linger "$USER"

systemctl --user daemon-reload
systemctl --user enable --now quests-server.service
systemctl --user enable --now quests-telegram.service   # если бот здесь

systemctl --user status quests-server.service
systemctl --user status quests-telegram.service
```

Логи:

```bash
journalctl --user -u quests-server.service -f
journalctl --user -u quests-telegram.service -f
```

`quests-overlay.service` на сервере **не** включай (нужен Wayland).

---

## 5. Рабочая станция (HUD)

На машине с niri / Wayland, в unit оверлея или в `.env` / `data/overlay.json`:

```bash
# Environment= в quests-overlay.service или export перед запуском:
QUESTS_API=http://SERVER_IP:8765
QUESTS_WEB_URL=http://SERVER_IP:8765
```

Либо в `data/overlay.json`:

```json
{
  "api_base": "http://SERVER_IP:8765"
}
```

(`QUESTS_API` имеет приоритет над файлом.)

Перезапуск оверлея → чип **HUD** в веб-форме станет зелёным.

---

## 6. Обновление на сервере

```bash
cd ~/Quests
git pull
./scripts/bootstrap.sh          # deps + migrate
./scripts/build-frontend.sh
systemctl --user restart quests-server.service
systemctl --user restart quests-telegram.service   # если включён
```

---

## Порядок (кратко)

| # | Где | Действие |
|---|-----|----------|
| 1 | сервер | `git clone` → `bootstrap` → `build-frontend` |
| 2 | сервер | `.env` (`QUESTS_HOST=0.0.0.0`, TG-токены) |
| 3 | сервер | firewall :8765 |
| 4 | сервер | `enable --now quests-server` (+ `quests-telegram`) |
| 5 | ПК | `QUESTS_API` / `api_base` → оверлей |
| 6 | браузер | `http://SERVER_IP:8765` — проверить API/HUD/Bot |

Проверка здоровья: `GET http://SERVER_IP:8765/api/health`.
