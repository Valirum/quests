# Quests HUD (Android)

Этап 1 квеста «Подумать над оверлеем под андроид» (quest=192): foreground
service с ongoing-уведомлением, без полноценного overlay. Тот же REST API,
что и десктопный HUD-оверлей на niri (см. note=3).

## Сборка

Нужны JDK 17, Android SDK (`sdk.dir` в `local.properties` или `ANDROID_HOME`).
`gradlew`/`gradle-wrapper.jar` уже в репо:

```bash
cd android
./gradlew assembleDebug
```

Установка на подключённое устройство/эмулятор:

```bash
./gradlew installDebug
```

Debug ставится как отдельное приложение `com.quests.hud.debug`
(`applicationIdSuffix = ".debug"`), рядом с релизом `com.quests.hud` —
иначе `INSTALL_FAILED_VERSION_DOWNGRADE` / конфликт подписи с CI-APK.
На лаунчере — «Quests HUD (debug)». Методичка по USB-отладке: note=65.

## Что уже есть

- `HubActivity` — свайп-хаб: настройки + SPA журнала.
- Экран настроек: `API URL` + `QUESTS_API_TOKEN`, проверка
  `/api/auth/state` + `/api/health`, prefs в `SharedPreferences`
  (`data/PrefsStore.kt`).
- `service/QuestsService.kt` — foreground service:
  - ongoing-уведомление (`quests_hud`, LOW) со списком активных квестов;
  - heads-up по major-событиям (`quests_events`, HIGH) — create/start/
    expire/complete/fail (quest=269), полл `GET /api/events?since=`;
  - actions: отложить 15/30/60 мин (как сайт) / завершить.
- `net/ApiClient.kt` — HttpURLConnection + bearer, без OkHttp.
- Методичка USB-отладки: note=65.

## Известные пробелы

- WebSocket `/ws` вместо полла events (полл достаточен, но с задержкой
  и таймаутами на медленном шлюзе).
- Chooser 90/120 мин для «Отложить» (сейчас на started/expired — 15/30).
- Floating overlay (quest=195).

## Релизы (CI, quest=197)

`.github/workflows/android.yml` — пуш в `main` с изменениями в `android/**`
(или ручной запуск) собирает подписанный `assembleRelease`, версия
`versionCode` = номер запуска (`github.run_number`, всегда возрастает,
руками трогать не надо), `versionName` — как в `app/build.gradle.kts`
(бампается вручную при осмысленном релизе). APK публикуется как GitHub
Release (`android-<versionName>-<run>`) и как build-артефакт.

Подпись — отдельный release-ключ (не debug), передаётся через секреты
репозитория (Settings → Secrets and variables → Actions):

| Секрет | Что |
|---|---|
| `QUESTS_RELEASE_KEYSTORE_B64` | `base64 -w0 quests-release.jks` |
| `QUESTS_RELEASE_KEYSTORE_PASSWORD` | пароль хранилища (PKCS12 → он же пароль ключа) |
| `QUESTS_RELEASE_KEY_ALIAS` | алиас ключа в хранилище |
| `QUESTS_RELEASE_KEY_PASSWORD` | пароль ключа (для PKCS12 = пароль хранилища) |

Без ключа `assembleRelease` собирается локально и без CI (для ручной
проверки), но выходит неподписанным — `signingConfig` подставляется только
когда `QUESTS_RELEASE_KEYSTORE_PATH` в окружении.

**Ключ бэкапить отдельно и не терять**: он определяет, что Android считает
«тем же приложением» для обновлений. Потеря ключа = все, кто уже поставил
APK, не смогут обновиться поверх — только переустановка.
