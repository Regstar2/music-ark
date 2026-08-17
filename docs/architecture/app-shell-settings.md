# App Shell, Account и Settings — v0.9.0

## Назначение

v0.9.0 добавляет presentation/application-shell boundary поверх существующих музыкальных модулей. Matching, Variant, Coverage, Download, Controlled Sync, Metadata Editor и Local Library не меняют свои backend-контракты.

## Global account state

Flutter использует `AccountSessionController` на базе `ChangeNotifier`. `SessionAwareMusicArkBridge` делегирует все операции существующему `MusicArkBridgeClient`, но для payload с `session` синхронно обновляет общий account state.

Это даёт один источник состояния для global account control и Yandex UI без отдельного state-management framework. Login/logout остаются операциями существующего Yandex application boundary. Cache-first `bootstrap()` остаётся источником профиля при старте и не выполняет обязательный network request.

При signed-in payload без account data контроллер сохраняет уже известный cached profile. Signed-out payload очищает профиль и увеличивает `logoutRevision`; shell использует эту ревизию только для сброса Yandex page после logout. Обычные theme/locale rebuild не меняют ключ Yandex page и не должны сбрасывать открытый playlist.

## Avatar contract

В проекте закреплён `yandex-music==3.0.0`. Фактически используемый account boundary — `client.me.account`. Документированный `Account` contract содержит `uid`, `login`, `full_name`, `display_name` и другие account fields, но не содержит подтверждённого публичного avatar URI.

Поэтому v0.9.0 не придумывает `avatar`, `picture` или URL-шаблон Яндекса и не передаёт credentials во Flutter. Fallback:

```text
displayName available → до двух инициалов
displayName unavailable → generic user icon
```

Если в будущей pinned dependency появится подтверждённый публичный avatar contract, его можно добавить в provider-independent account DTO отдельной задачей.

## Settings persistence

UI-only preferences не изменяют MusicArk SQLite schema. Typed JSON store хранится в пользовательском `.musicark/ui_preferences.json` и содержит только:

```text
schemaVersion = 1
themeMode     = system | light | dark
localeMode    = system | ru | en
```

Store не содержит token, provider credentials, library paths или содержимое коллекции.

## Theme

`AppTheme` централизует light/dark `ThemeData` на Material 3 `ColorScheme`. `MaterialApp.themeMode` получает значение из `AppSettingsController`:

```text
system → ThemeMode.system
light  → ThemeMode.light
dark   → ThemeMode.dark
```

Feature widgets должны использовать `Theme.of(context).colorScheme` вместо новых hard-coded light/dark backgrounds.

## Localization

Flutter localization pipeline использует `flutter_localizations`, `gen_l10n`, `l10n.yaml` и ARB resources для `ru`/`en`. При `localeMode=system` поддерживаются системные `ru` и `en`; для другого системного языка fallback детерминированно равен `ru`.

Новые shell/account/settings/help/about surfaces используют generated `AppLocalizations`. Исторические feature widgets, в которых строки были встроены напрямую до v0.9.0, должны переноситься в ARB без изменения backend values, metadata, filenames, provider data и internal codes.

## Help / About

Help хранится локально в ARB и не требует web request. About использует единый `AppInfo` для app/backend/schema version и показывает безопасную diagnostic information. Clipboard payload содержит только version/schema/OS/theme/locale и не содержит credentials, protected URLs или данные пользовательской библиотеки.

## Now Playing

Settings, Help и About находятся в том же shell `IndexedStack`. `MusicArkNowPlayingBar` расположен ниже него и остаётся частью shell при переходах между utility pages. Theme/locale меняют presentation, но не создают новый playback engine.

## Non-goals

v0.9.0 не добавляет Yandex Upload, новый matcher, новый playback engine, mobile UI, telemetry, cloud account MusicArk или новую SQLite migration.
