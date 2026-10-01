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

- `MainActivity` — экран настроек: `API URL` + `QUESTS_API_TOKEN`,
  проверка через `GET /api/auth/state` + `GET /api/health` перед
  сохранением. Хранение — `EncryptedSharedPreferences`
  (`data/PrefsStore.kt`).
- `service/QuestsService.kt` — foreground service с заглушкой
  ongoing-уведомления. Поллинг `/api/quests` и рендер реальных данных —
  следующие шаги квеста (716/717).
- `net/ApiClient.kt` — минимальный HTTP-клиент (bearer-токен, без внешних
  зависимостей вроде OkHttp).

## Известные пробелы (следующие шаги квеста 192)

- Поллинг активных квестов (шаг 716) не подключён к сервису — `ApiClient`
  есть, но `QuestsService` его пока не вызывает.
- Рендер уведомления (717), тап-действие на конкретный квест (718),
  battery optimization exemption (719) — не сделаны.
- `POST_NOTIFICATIONS` runtime permission (Android 13+) запрашивается не
  сама — надо добавить `ActivityResultContracts.RequestPermission` в
  `MainActivity` перед стартом сервиса.

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
