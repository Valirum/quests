# Quests HUD (Android)

Этап 1 квеста «Подумать над оверлеем под андроид» (quest=192): foreground
service с ongoing-уведомлением, без полноценного overlay. Тот же REST API,
что и десктопный HUD-оверлей на niri (см. note=3).

Не собиралось и не запускалось в этой сессии — нет Android SDK/Gradle/adb в
окружении, где писался код. Первая сборка и отладка — на твоей машине.

## Сборка

Нужны JDK 17+, Android SDK (`ANDROID_HOME`), Gradle. Обёртки `gradlew` в
репо нет — либо ставь системный `gradle` и гоняй им, либо один раз
сгенерируй обёртку:

```bash
cd android
gradle wrapper --gradle-version 8.7
./gradlew assembleDebug
```

Установка на подключённое устройство/эмулятор:

```bash
./gradlew installDebug
```

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
