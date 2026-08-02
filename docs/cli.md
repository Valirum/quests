# Quests CLI

Клиент журнала: квесты через локальный API и хуки (скрипт / webhook / unix socket).

```bash
uv run quests --help          # или: quests -h
uv run quests list --help
uv run quests hook --help
```

После `uv sync` / `./scripts/bootstrap.sh` команда `quests` доступна в окружении проекта.

Нужен запущенный API (`./scripts/run-server.sh`), кроме команд `hook *` — они работают с файлом напрямую.

| Env | Default | Назначение |
|-----|---------|------------|
| `QUESTS_API` | `http://127.0.0.1:8765` | база API |
| `QUESTS_HOOKS` | `data/hooks.json` | хранилище хуков |

## `--json` / `-h`

- `-h` / `--help` — у корня и у каждой подкоманды (argparse).
- `--json` — машиночитаемый ответ в stdout (ошибки тоже JSON в stderr: `{"ok":false,"error":"…"}`).

```bash
quests --json list
quests list --json
quests show 3 --json | jq .title
```

## Квесты

| Команда | Что делает |
|---------|------------|
| `list` / `ls` | список (`--status`, `--pinned` / `--unpinned`) |
| `show` / `get ID` | детали + шаги |
| `add TITLE` | создать (`-d`, `--pin`, `--significance`, `--step`×N) |
| `pin ID` / `unpin ID` | булавки (`pin --off`) |
| `status ID STATUS` | `active\|delayed\|completed\|failed\|archived` |
| `complete ID` | → completed |
| `fail ID` | → failed |
| `step ID` | +1 к шагу (или `--inc N` / `--set N` / `--done`; `--step-id` / `--title`) |
| `delete` / `rm ID` | удалить |

Примеры:

```bash
quests add "Собрать травы" --pin --step "Луговая" --step "Горная"
quests step 4 --title лугов --inc 2
quests complete 4 --json
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
