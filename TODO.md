# Quests — MVP TODO

Стек: Python · FastAPI · SQLite · Svelte (Vite) · GTK4 + gtk4-layer-shell · Telegram  
Окружение: CachyOS · niri (Wayland)

## Точки входа

- API + SPA (dist): `./scripts/run-server.sh` → [http://127.0.0.1:8765](http://127.0.0.1:8765)
- Фронт с HMR: `./scripts/run-frontend.sh` → [http://127.0.0.1:5173](http://127.0.0.1:5173) (нужен API)
- Сборка SPA: `./scripts/build-frontend.sh`
- Оверлей: `./scripts/run-overlay-smoke.sh` / `python -m overlay`
- HUD input: `python -m overlay toggle` · монитор: `python -m overlay monitor`
- CLI: `uv run quests --help` · [`docs/cli.md`](docs/cli.md)
- Telegram-бот: `./scripts/run-telegram.sh` (секреты в `.env`; `/new-llm` → Cursor API)

---

## 0. Smoke / инфра

- [x] Системные зависимости (`gtk4`, `gtk4-layer-shell`, `python-gobject`)
- [x] `pyproject.toml` + uv + `scripts/bootstrap.sh`
- [x] Минимальный layer-shell smoke → `overlay/smoke.py`
- [x] Проверено на niri



## 1. Ядро API

- [x] Модель: Quest + QuestStep, `pinned`, статусы вкл. `delayed`, `deadline_at` / `duration_seconds`
- [x] SQLite + seed
- [x] CRUD `/api/quests` (+ `?pinned=`, `?status=`), health
- [x] PATCH шага `/api/quests/{id}/steps/{step_id}`
- [x] Автостатус: все шаги done → `completed`; откат шага → `active`
- [x] Live: WebSocket `/ws` + `/api/sync` + `/api/events` (kinds, toast/sound)
- [x] UI-фокус квеста: `POST /api/ui/focus-quest` (+ `pending_focus` для новых вкладок)
- [x] Миграции Alembic (`alembic/`, `./scripts/migrate.sh` / `uv run quests-migrate`, auto-upgrade в `init_db`; новые: `uv run alembic revision --autogenerate -m "…"`)



## 2. Веб-журнал (SPA)

- [x] Vite + Svelte; layout список / детали; gruvbox-yellow токены
- [x] Модалки create/edit; удаление из модалки и из шапки детали
- [x] Быстрые действия: Выполнено/Активно, `+`/`−` по шагам (без модалки)
- [x] Live-обновление по WS; `?quest=` + HUD → выбор квеста
- [x] Значимость квеста: common/uncommon/epic/legendary → major «Получено {…} задание» + цвет
- [x] FastAPI отдаёт `frontend/dist` (после `build-frontend.sh`)
- [x] Dev: Vite на `:5173`, proxy `/api` + `/ws`, `host: 127.0.0.1`
- [x] Разделы списка: избранные, близкие к завершению, фильтры побогаче
- [x] Веб: поиск (раскладка + fuzzy≥4) вместо фильтра; булавки Carbon; кнопки Выполнено/Активно



## 3. Оверлей

- [x] HUD: избранное + срочные (окно дедлайна); таймер слева (green/orange/red); толстый разделитель
- [x] Веб: срок/длительность (local ↔ UTC в БД/API с `Z`); таймер в карточке и детали (`осталось / длительность`); скрытие после истечения
- [x] Авто-просрочка: `active` + истёкший `deadline_at` → `delayed` (failed вручную)
- [x] Passthrough: текст + chip-фон; interactive: панель + drag-ручка + кликабельные тайтлы
- [x] Input region sync (Wayland); IPC toggle / monitor / status
- [x] Мультимонитор: кнопка цикла + drag HUD в пределах монитора (без выезда за край)
- [x] Interactive keys: Esc→passthrough, Space→монитор, arrows/hjkl→сдвиг
- [x] Клик по тайтлу → WS focus-quest + подъём окна через `niri focus-window` (по title); иначе `xdg-open ?quest=`
- [x] Major (центр) + minor (угол); fantasy pack; JetBrains Mono; major VO (`paplay`)
- [x] Toggle show/hide всего оверлея (CLI / хоткей niri)
- [x] HUD collapse: ─ / Backspace → только «Задачи» (+ выход из interactive); interactive → auto-expand
- [ ] `quest_appeared` без major-тоста на ручной create (отдельный kind для inbound)
- [x] Cyberpunk style pack (CP2077 ref: red headers / yellow objectives / hard edges); fantasy остаётся default
- [x] Style switcher в HUD (dropdown) + CSS hot-reload; `data/overlay.json` (style_pack, monitor, margins)
- [ ] Другие style packs
- [x] Namespace / `layer-rule` в niri (README: `quests-overlay|major|minor`)



## 4. Периодика (дейлики / RRULE-подобное)

Решение: **шаблон + инстансы**

- [x] Модель шаблона (freq: daily/weekly, steps, pin, `deadline_time` + duration, tz, weekdays)
- [x] Материализация инстанса на период (`periodic.materialize_due` + фон + list/get)
- [x] UI: модалка «Шаблоны» + бейдж `period_key` у инстансов
- [ ] Стрики / пропуски (минимум) — §7
- [x] Тип шаблона с кастомным emit: шанс + рандомное время внутри периода (сюрприз-квест, напр. «встать / разминка»)



## 5. Награды / штрафы / метрики

- [x] Сущности-метрики (`xp`, импульс, шестёрка характеристик)
- [x] Правила reward/penalty на complete / fail / delay (+ expire)
- [ ] Опциональный текстовый флавор поверх числа (частично в ledger)
- [x] UI раздел «Лист» + дофамин-оформление



## 6. CLI + хуки

- [x] CLI (`quests list|show|add|pin|step …`) — argparse; `-h` / `--help`; см. [`docs/cli.md`](docs/cli.md)
- [x] Хуки: global **и** на квест; `complete` / `step` / `status` (+ kinds) → script / webhook / socket
- [x] Машиночитаемый вывод CLI (`--json`)



## 7. Статистика

- [ ] Агрегации, стрики периодики, completed/failed/delayed
- [ ] Экран / `/api/stats`



## 8. Telegram-бот (телефон: список / статус / пуши)

Цель: смотреть активные задачи с телефона, минимально управлять, получать уведомления.  
Стек остаётся локальным (API+БД на хосте); бот — клиент к API. Исходящий Telegram API — **только через HTTP(S)-прокси**.

### 8.1 Инфра

- [x] Пакет/модуль бота (`quests-telegram` / `src/quests/telegram/`), зависимость (aiogram или python-telegram-bot)
- [x] Конфиг: `QUESTS_TG_TOKEN`, whitelist `QUESTS_TG_USER_IDS` (один/несколько)
- [x] Прокси обязателен для вызовов Telegram: дефолт `http://127.0.0.1:12334`; override ключом CLI (`--proxy`) и/или env (`QUESTS_TG_PROXY`)
- [x] База API: `QUESTS_API` (как у CLI), дефолт `http://127.0.0.1:8765`
- [x] Точка входа + script; отказ стартовать без token / без доступного прокси (явная ошибка)
- [x] Игнор апдейтов от чужих user id

### 8.2 Команды и просмотр

- [x] `/start`, `/help` — кратко по командам
- [x] Активные задачи **по категориям** (команда списка + группировка; без категории — отдельно)
- [x] Карточка квеста: title, статус, категория, дедлайн/осталось, шаги (кратко)

### 8.3 Управление

- [x] Создание задачи **диалогом** (Conversation: title → опц. категория / дедлайн-длительность → confirm → `POST /api/quests`)
- [x] Инлайн-клавиатура смены статуса на карточке/в списке: как минимум active / completed / failed / delayed (набор уточнить по UX)
- [x] Callback’и идемпотентны; после смены — обновить сообщение + клавиатуру

### 8.4 Уведомления

Подписка на события API (WS `/ws` и/или `/api/events` + локальный трекер «уже уведомили»).

- [x] **Старт окна задачи** (есть `deadline_at` + `duration_seconds`): момент `deadline − duration` → пуш «задача началась / таймер пошёл»
- [x] **Просрочка**: переход в `delayed` / expire
- [x] **Провал**: статус `failed`
- [x] **Выполнение**: статус `completed`
- [x] (желательно) новый инстанс периодики / сюрприз — тем же каналом, что major/appear
- [x] Дедуп пушей: `(quest_id, kind)` не слать повторно

### 8.5 Потом (бот)

- [x] Чек шагов из TG
- [ ] Настройки «какие kinds слать»
- [ ] systemd user-unit рядом с `quests-server`

### 8.6 LLM → квест (текст + голос)

По умолчанию **Cursor Agent API** (`CURSOR_API_KEY`, cloud без репо → JSON). Ollama остаётся опциональным (`QUESTS_LLM_PROVIDER=ollama`).
Голос: **faster-whisper** (`QUESTS_WHISPER_MODEL=small|medium|large`, default **small**) → `/new-llm`.

- [x] Модуль `quests.llm`: schema / client / draft→API body
- [x] Провайдер Cursor (`Agent.prompt` + cloud empty workspace)
- [x] TG: `/new-llm` + кнопка «✨ LLM», уточнение, confirm inline
- [x] CLI: `quests llm-add "…"` (`-y` без подтверждения)
- [x] STT: `quests.stt` + TG voice/audio (в диалоге и вне → LLM)
- [ ] systemd / автоподъём рядом с ботом



## 9. Потом

- [ ] Плагин noctalia
- [x] Категории / типы квестов (сюжет, быт, привычка…)
- [x] Упростить сайдбар: чекбокс «Показать все» (иначе только активные); неактивные — перечёркиванием; снизить вложенность раздел/квестлайн