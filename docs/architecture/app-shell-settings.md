# App Shell, Account и Settings — v0.9.x

## Назначение

v0.9.x поддерживает presentation/application-shell boundary поверх существующих музыкальных модулей. Matching, Variant, Coverage, Download, Controlled Sync, Metadata Editor и Local Library не меняют свои backend-контракты из-за utility UI.

v0.9.7 завершает polish utility-разделов `Settings`, `Help` и `About`, не создавая новый routing/state-management слой.

## Global account state

Flutter использует `AccountSessionController` на базе `ChangeNotifier`. `SessionAwareMusicArkBridge` делегирует все операции существующему `MusicArkBridgeClient`, но для payload с `session` синхронно обновляет общий account state.

Это даёт один источник состояния для global account control, Settings provider card и Yandex UI без отдельного state-management framework. Login/logout остаются операциями существующего Yandex application boundary. Cache-first `bootstrap()` остаётся источником профиля при старте и не выполняет обязательный network request.

При signed-in payload без account data контроллер сохраняет уже известный cached profile. Signed-out payload очищает профиль и увеличивает `logoutRevision`; shell использует эту ревизию только для сброса Yandex page после logout. Обычные theme/locale rebuild не меняют ключ Yandex page и не должны сбрасывать открытый playlist.

## Avatar contract

В проекте закреплён `yandex-music==3.0.0`. Фактически используемый account boundary — `client.me.account`. Документированный `Account` contract содержит `uid`, `login`, `full_name`, `display_name` и другие account fields, но не содержит подтверждённого публичного avatar URI.

Поэтому MusicArk не придумывает `avatar`, `picture` или URL-шаблон Яндекса и не передаёт credentials во Flutter. Fallback:

```text
displayName available → до двух инициалов
displayName unavailable → generic user icon
```

v0.9.7 Settings provider card использует тот же contract; отдельный avatar/login source не вводится.

Если в будущей pinned dependency появится подтверждённый публичный avatar contract, его можно добавить в provider-independent account DTO отдельной задачей.

## Settings persistence

UI-only preferences не изменяют MusicArk SQLite schema. Typed JSON store хранится в пользовательском `.musicark/ui_preferences.json` и содержит только:

```text
schemaVersion = 1
themeMode     = system | light | dark
localeMode    = system | ru | en
```

Store не содержит token, provider credentials, library paths или содержимое коллекции.

v0.9.7 только меняет presentation этих настроек: отдельная карточка с пояснением об автосохранении заменена компактным status chip, а theme/locale selectors reflow в зависимости от доступной ширины.

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

Новые shell/account/settings/help/about surfaces используют generated `AppLocalizations`. Provider data, local paths, filenames, IDs и backend codes не переводятся.

v0.9.7 расширяет Help в обоих ARB одинаковым набором из одиннадцати тем. Справка остаётся offline и не получает второй localization store.

## Utility page layout — v0.9.7

Settings, Help и About используют центральный content container с максимальной шириной около `1180 px` и общий `AppUiTokens.pagePadding`. Это не mobile redesign: `LayoutBuilder` только reflow существующие desktop controls, когда shell предоставляет меньше места.

```text
large desktop
  → constrained content
  → wide preference/action rows
  → About two-column environment data

narrow desktop
  → the same content model
  → stacked controls/actions
  → About one-column environment data
```

Help группирует темы в четыре секции и использует компактные `ExpansionTile` rows. About переиспользует существующий vector `MusicArkMark`.

## Help / About navigation

Help и About остаются в том же shell `IndexedStack`, что и раньше. v0.9.7 передаёт им явный callback возврата в Settings и показывает его как breadcrumb/back action.

Это не новый Navigator/router. Переход utility page → Settings меняет только существующий shell index и не пересоздаёт Yandex workspace, account session или Now Playing.

## Help content boundary

Help хранится локально в ARB и описывает подтверждённые current-source semantics:

- provider library vs local index;
- Identity vs Metadata vs Variant;
- Missing vs Different Version;
- ORIGINAL/CENSORED and Variant acceptance;
- explicit Download tasks;
- confirmation-protected Controlled Sync;
- Metadata Editor as explicit write boundary;
- artwork/playback-cache behavior;
- UI settings persistence;
- data-safety model.

Help не является отдельным business-rule source. При изменении доменного поведения соответствующая справка должна обновляться вместе с основной документацией/тестами.

## About / diagnostics

About использует единый `AppInfo` для app/backend/schema version и показывает version/environment, dependency licenses и project repository.

Clipboard diagnostics содержит только:

```text
app version
backend version
database schema
OS
theme
locale
```

Он не содержит credentials, protected URLs, library paths/list/content.

v0.9.7 не добавляет external-URL dependency только ради GitHub action. Repository URL остаётся selectable и доступен через явное copy-link действие.

## Now Playing

Settings, Help и About находятся в том же shell `IndexedStack`. `MusicArkNowPlayingBar` расположен ниже него и остаётся частью shell при переходах между utility pages. Theme/locale меняют presentation, но не создают новый playback engine.

## Non-goals

v0.9.7 не добавляет Yandex Upload, новый matcher, новый playback engine, mobile UI, telemetry, cloud account MusicArk, новую SQLite migration, routing framework или новый settings/account backend.
