# Деплой: GitHub Actions → SSH (замена Watchtower)

Раньше сервер сам поллил GHCR (Watchtower, 60–300с). Теперь `deploy`-job в
`.github/workflows/main.yml` после зелёного `build-images` на пуше в `main`
сам заходит на сервер по SSH и гонит `deploy/docker/ci-deploy.sh` — деплой
привязан к конкретному коммиту, а не к таймеру.

## Ключ уже сгенерирован и стоит на сервере

Отдельный ed25519-ключ (не личный), приватная часть — **только** у тебя, я её
не сохранял нигде кроме как отдать сейчас. Публичная часть уже добавлена в
`~/.ssh/authorized_keys` на 192.168.1.11 с ограничением:

```
command="bash /home/amarant/Documents/projects/quests/deploy/docker/ci-deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAAC3... quests-ci-deploy
```

Т.е. даже если приватный ключ утечёт из GitHub Secrets — им можно **только**
перезапустить деплой из `origin/main`, никакой произвольный shell.

## Что добавить в GitHub (Settings → Secrets and variables → Actions → New repository secret)

| Имя секрета | Значение |
|---|---|
| `DEPLOY_SSH_HOST` | `192.168.1.11` |
| `DEPLOY_SSH_USER` | `amarant` |
| `DEPLOY_SSH_KEY` | приватный ключ целиком, весь файл `quests_ci_deploy` (включая `-----BEGIN...` / `-----END...` строки) |

Приватный ключ лежит у меня в `/tmp/claude-1000/.../deploy-key/quests_ci_deploy`
(scratch-директория сессии) — скопируй его содержимое в секрет и потом смело
сотри файл, он больше не нужен нигде кроме GitHub Secrets и `authorized_keys`
на сервере.

## Проверка

После добавления секретов — любой пуш в `main` (или ре-ран последнего workflow
run в Actions UI) прогонит job `deploy`. Смотреть: Actions → **CI** → последний
ран → job `deploy`.

Ручками, в обход CI, то же самое можно прогнать прямо на сервере:

```bash
bash /home/amarant/Documents/projects/quests/deploy/docker/ci-deploy.sh
```

## Если нужно отозвать ключ

Удалить соответствующую строку из `~/.ssh/authorized_keys` на сервере — без
доступа к самому серверу ключ бесполезен (это не токен API, а SSH-ключ,
центрального реестра для отзыва нет).
