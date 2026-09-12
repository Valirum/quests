# Деплой: self-hosted GitHub Actions runner (замена Watchtower)

Раньше сервер сам поллил GHCR (Watchtower, 60–300с). Теперь `deploy`-job в
`.github/workflows/main.yml` после зелёного `build-images` на пуше в `main`
сам гонит `deploy/docker/ci-deploy.sh` — деплой привязан к конкретному
коммиту, а не к таймеру.

## Почему self-hosted, а не SSH из облачного раннера

Первая версия дёргала сервер по SSH из обычного `ubuntu-latest`-раннера — не
взлетело: `192.168.1.11` приватный адрес, у GitHub-раннеров в облаке до него
физически нет маршрута. Раннер живёт прямо на сервере — деплой-шаг просто
локально выполняет `ci-deploy.sh`, никакого SSH-хопа.

## !!! Важно про безопасность — репо публичный !!!

GitHub прямым текстом предупреждает: self-hosted раннер на публичном репо —
дыра, если он видит `pull_request`-события (форк открывает PR → его код
исполняется на твоём железе). У нас это закрыто тем, что джоба `deploy`
гейтится **строго** на прямой пуш в `main`:

```yaml
if: |
  github.event_name == 'push' && github.ref == 'refs/heads/main' &&
  needs.build-images.result == 'success'
```

Форк не может запушить в `main` — write-доступ есть только у владельца репо.
Правила, которые нельзя нарушать (иначе self-hosted реально станет дырой):

- не вешать `self-hosted` на `changes`/`test` — они реагируют и на чужие PR
- никогда не заводить `pull_request_target` в этом файле
- не расширять `deploy`'s `if:` на что-либо, кроме прямого пуша в `main`

Подробный комментарий с тем же текстом лежит прямо над джобой в
`.github/workflows/main.yml` — читать его перед любой правкой триггеров.

## Установка раннера на сервере

Регистрационный токен разовый (~1 час), берётся в GitHub UI:
**Settings → Actions → Runners → New self-hosted runner** (Linux x64) —
дальше используется одноразово при `config.sh`, для повседневной работы
раннера не нужен (сервис сам обновляет свою сессию).

Раннер поднят как systemd-сервис (`actions.runner.*.service`) под пользователем
`amarant`, с доступом к docker (в группе `docker`) и к чекауту репозитория
в `~/Documents/projects/quests`.

## SSH-ключ (`DEPLOY_SSH_KEY` / `DEPLOY_SSH_HOST` / `DEPLOY_SSH_USER`) — больше не используется деплоем

Это была первая (нерабочая для облачного раннера) версия. Сам forced-key в
`~/.ssh/authorized_keys` на сервере оставлен как ручной резервный путь —
можно всё ещё дёрнуть деплой без раннера:

```bash
ssh -i quests_ci_deploy amarant@192.168.1.11
```

GitHub-секреты `DEPLOY_SSH_*` можно удалить (Settings → Secrets → Actions) —
CI ими больше не пользуется, лежат мёртвым грузом.

## Проверка

Любой пуш в `main` (или ре-ран последнего workflow run в Actions UI) прогонит
job `deploy` на самом раннере. Смотреть: Actions → **CI** → последний ран →
job `deploy`.

Ручками, в обход CI, то же самое можно прогнать прямо на сервере:

```bash
bash /home/amarant/Documents/projects/quests/deploy/docker/ci-deploy.sh
```
