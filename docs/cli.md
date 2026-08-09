# Quests CLI

Клиент журнала: квесты через локальный API и хуки (скрипт / webhook / unix socket).

```bash
uv run quests --help          # или: quests -h
uv run quests list --help
uv run quests hook --help
```

После `uv sync` / `./scripts/bootstrap.sh` команда `quests` доступна в окружении проекта.

Нужен запущенный API (`./scripts/run-server.sh`), кроме команд `hook *` — они работают с файлом напрямую.

| Env / флаг | Default | Назначение |
|-----|---------|------------|
| `QUESTS_API` / `--api URL` | `http://127.0.0.1:8765` | база API (`--api` перекрывает env) |
| `QUESTS_HOOKS` | `data/hooks.json` | хранилище хуков |
| `QUESTS_LLM_PROVIDER` | `cursor` | `cursor` \| `ollama` |
| `CURSOR_API_KEY` | — | ключ Cursor (Dashboard → API Keys) |
| `QUESTS_LLM_MODEL` | `composer-2.5` | модель Cursor / Ollama |
| `QUESTS_LLM_BASE` | `http://127.0.0.1:11434` | только для `ollama` |
| `QUESTS_LLM_TIMEOUT` | `180` | таймаут сек |

## `--json` / `--api` / `-h`

- `-h` / `--help` — у корня и у каждой подкоманды (argparse).
- `--json` — машиночитаемый ответ в stdout (ошибки тоже JSON в stderr: `{"ok":false,"error":"…"}`).
- `--api URL` — база API (перекрывает `QUESTS_API`); можно до или после подкоманды.

```bash
quests --json list
quests list --json
quests --api http://192.168.1.11:8765 list
quests show 3 --json | jq .title
```

## Квесты

| Команда | Что делает |
|---------|------------|
| `list` / `ls` | список (`--status`, `--pinned` / `--unpinned`, `--category`, `--questline`) |
| `show` / `get ID` | детали + шаги (+ раздел / квестлайн) |
| `add TITLE` | создать (`-d`, `--pin`, `--significance`, `--step`×N, `--category`, `--questline`) |
| `llm-add TEXT…` | свободный текст → Cursor/Ollama → квест (`-y` без confirm) |
| `set ID` | поля: `--title` / `-d` / `--category` / `--questline` / `--significance` (`none` снимает) |
| `pin ID` / `unpin ID` | булавки (`pin --off`) |
| `status ID STATUS` | `active\|delayed\|completed\|failed\|archived` |
| `complete ID` | → completed |
| `fail ID` | → failed |
| `step ID` | +1 к шагу (или `--inc N` / `--set N` / `--done`; `--step-id` / `--title`) |
| `step-add QUEST TITLE` | добавить шаг (`--total`, `--progress`, `--sort-order`, `-d`, `--quiet`) |
| `step-edit QUEST STEP` | поля шага (`--title` / `-d` / `--total` / `--set` / `--sort-order`) |
| `step-rm QUEST STEP` | удалить шаг (нельзя единственный) |
| `delete` / `rm ID` | удалить |

Примеры:

```bash
quests add "Собрать травы" --pin --step "Луговая" --step "Горная"
quests add "MVP" --category work --questline "Проект"
quests set 4 --category health
quests set 4 --questline none
quests step 4 --title лугов --inc 2
quests step-add 4 "Новый шаг" --total 3
quests step-edit 4 12 --title "Переименован" --total 5
quests step-rm 4 12
quests complete 4 --json
```

## Разделы и квестлайны

| Команда | Что делает |
|---------|------------|
| `categories` / `cats` | справочник разделов (slug, label, color) |
| `questline list` / `ql ls` | список линий (`--category`) |
| `questline show ID` | детали |
| `questline add TITLE` | создать (`--category`, `--color`, `--icon`) |
| `questline set ID` | изменить (`--title` / `-d` / `--category` / `--color` / `--icon`) |
| `questline delete ID` | удалить (квесты отвяжутся, категория у них останется) |

`--category` / `--questline` принимают `id`, `slug`/`label` (для раздела), подстроку title (для линии) или `none`/`-`/`нет` для сброса. Участник квестлайна всегда получает категорию линии.

```bash
quests categories
quests questline add "Проект Quests" --category work --icon flag --color '#5a8a9a'
quests ql list --category work
quests ql set 1 --category health   # sync category у участников
```

## Хуки: и global, и на квест

**Оба варианта.**

- Без `--quest` — **global**: срабатывает на любое событие нужного kind.
- С `--quest ID` — только события этого квеста.
- На одно событие могут сработать и global, и quest-хуки.

Типы:

| `--type` | Параметр | Поведение |
|----------|----------|-----------|
| `script` | `--command` | `shell=True`; JSON события в stdin; env `QUESTS_KIND`, `QUESTS_QUEST_ID`, `QUESTS_TITLE`, `QUESTS_DETAIL`, `QUESTS_PAYLOAD` |
| `webhook` | `--url` | `POST` `application/json` |
| `socket` | `--path` | unix stream, одна JSON-строка + `\n` |

События (`--event` / `-e`, можно несколько): aliases или сырые kinds.

```bash
quests hook events          # таблица aliases → kinds
quests hook events --json
```

Полезные aliases: `complete`, `step`, `status`, `fail`, `created`, `deleted` (см. также `on_complete` / `on_step` / `on_status_change`).

```bash
# global: любой complete
quests hook add -e complete -t script \
  -c 'notify-send "Квест" "$QUESTS_TITLE"'

# только квест #12
quests hook add -e step -e complete -t script --quest 12 \
  --name daily-ping \
  -c 'echo "$QUESTS_PAYLOAD" >> /tmp/quests-12.log'

# webhook
quests hook add -e fail -t webhook --url http://127.0.0.1:9000/hook

quests hook list
quests hook list --global
quests hook list --quest 12 --json
quests hook disable <id>
quests hook enable <id>
quests hook remove <id>
```

Хуки читает **сервер** при `hub.publish` (UI, CLI через API, expire, периодика). Файл подхватывается на каждый dispatch — перезапуск сервера не обязателен после `hook add`.

## Коды выхода

- `0` — ок  
- `1` — ошибка API / валидации / хук не найден  
- `2` — нет команды / argparse  
