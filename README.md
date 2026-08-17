# MusicArk

**Русский** · [English](README_EN.md)

**Текущая версия кода: 0.9.0 — UI, Account & Settings.**  
**Текущая схема SQLite: 1.8.4.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями; v0.9.0 добавляет единую оболочку приложения, глобальное состояние аккаунта, настройки, светлую/тёмную тему, RU/EN localization infrastructure, локальную справку и диагностический About.

## Desktop shell v0.9.0

В нижней части глобальной левой панели находятся `Настройки` и account control. Без сохранённой Yandex session показывается `Войти`, а при авторизации — имя аккаунта и fallback-аватар с инициалами. Вход использует существующий Yandex workflow; logout проходит через тот же backend boundary, что и раньше. Account bootstrap остаётся cache-first и не требует сетевого запроса при каждом запуске.

Настройки интерфейса применяются без перезапуска и сохраняются отдельно от музыкальной SQLite БД:

- тема: `Как в системе` / `Светлая` / `Тёмная`;
- язык: `Как в системе` / `Русский` / `English`;
- Help работает локально;
- About показывает версию приложения, backend/schema, ОС и безопасную диагностическую информацию без токенов и содержимого библиотеки.

MusicArk использует стандартные Flutter `ThemeMode`, Material 3 `ColorScheme` и `gen_l10n`/ARB resources. Смена theme/locale не пересоздаёт application shell и не должна сбрасывать текущий Yandex playlist или Now Playing.

## Основной цикл

```text
Yandex Library = desired state
        ↓
Local Library = actual files (обычный Scan только читает)
        ↓
Matching + Variant + Coverage
        ↓
Missing / Wanted → Download / Controlled Sync
```

Для файлов с плохими тегами используется отдельный ручной workflow:

```text
Local Library
  → Редактировать метаданные
  → локальная правка
      или
    Yandex Track search → Compare
  → Применить метаданные
      или
    Применить и связать
  → transactional MP3 write
  → single-file reindex + SHA-256
  → targeted Matching refresh
  → Coverage/UI refresh
```

## Metadata и Identity — разные сущности

**«Применить метаданные»** меняет только выбранные непустые поля, artwork и при явном выборе filename локального MP3. После записи выполняются single-file reindex, обновление SHA-256 и targeted Matching refresh. Даже высокая similarity сама по себе не становится подтверждённой identity.

**«Применить и связать»** выполняет ту же запись и дополнительно создаёт подтверждённую пользователем связь:

```text
provider   = yandex_music
external   = <Yandex Track ID>
local file = <Local File ID>
method     = exact_id
confidence = 1.0
reason     = user_confirmed
```

При таком bind MusicArk записывает доверенный provenance в ID3 TXXX. Зарезервированные provenance-теги нельзя редактировать через обычный раздел Advanced Tags.

## Безопасность изменения файлов

Scan, Matching, Coverage и Sync **не изменяют пользовательские аудиофайлы**. Существующий файл изменяется только после явного действия в Metadata Editor.

Для MP3 используется pipeline:

```text
original
  ↓
same-directory temporary copy
  ↓
ID3/artwork write
  ↓
MPEG audio validation
  ↓
metadata read-back validation
  ↓
atomic os.replace()
```

До atomic replace оригинал остаётся неизменным. Audio stream не транскодируется. Неизвестные/custom ID3 frames сохраняются, если пользователь явно не редактирует их.

## Artwork и Yandex Library playback

Local Library показывает thumbnail каждого трека. Приоритет: embedded artwork, затем уже cached Yandex artwork для подтверждённой identity, затем placeholder. Список локальной библиотеки не делает Yandex request для каждой строки.

В Yandex Library доступны artwork и встроенное воспроизведение. Backend готовит или переиспользует приватный playback cache под `.musicark/playback/yandex` и передаёт Flutter только локальный путь. Yandex token, Authorization headers и protected/signed provider media URL во Flutter не передаются. Playback cache не индексируется в Local Library и не влияет на Matching или Coverage.

Для Yandex workspace сохраняется минимальная ширина около `920 px`; более узкое окно использует horizontal scrolling. Это текущий safeguard, а не mobile/responsive redesign.

## Content labels и Variant acceptance

App-level метки **ОРИГИНАЛ / ЦЕНЗУРА** можно задавать для local track и cached Yandex identity. Они не меняют Yandex, не переписывают audio metadata, не меняют Matching identity и не повышают confidence.

Для `ALTERED`, `DIFFERENT_VERSION` и `UNCERTAIN` пользователь может выбрать **«Эта версия меня устраивает»** и позднее отменить принятие. Решение хранится отдельно от analyzer result: исходный Variant status не превращается в `SAME`. Принятие действительно только для того же analysis evidence/fingerprint.

## Форматы

Архитектура использует format adapters. Полноценная безопасная запись реализована для **MP3/ID3**. Другие аудиоформаты остаются read-only в Metadata Editor.

## Controlled Sync

Sync не является двунаправленным filesystem mirror. Стандартный Apply остаётся безопасным:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations = 0
```

Metadata Editor — отдельный explicit-write workflow и не вызывается Scan/Matching/Coverage/Sync автоматически.

## SQLite

Forward-only schema:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync
1.8.1 — Rich Yandex download metadata/provenance
1.8.2 — Local artwork cache / Metadata Editor support
1.8.3 — app-level ORIGINAL/CENSORED labels
1.8.4 — variant user acceptance
```

v0.9.0 не повышает SQLite schema: theme/locale preferences хранятся отдельным UI-only typed store. Инициализация БД остаётся idempotent и не требует удаления существующей `.musicark/musicark.db`.

## Запуск для разработки на Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -p "test_*.py" -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

## Roadmap

```text
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata       complete
v0.9.0 — UI, Account & Settings                        current
v0.10.x — Yandex Upload                                next
```

Yandex Upload в v0.9.0 не реализован. Это состояние исходного кода, а не заявление об опубликованном GitHub Release. См. `docs/versions/v0.9.0.md`, `docs/architecture/app-shell-settings.md`, `docs/architecture/metadata-editor.md`, `docs/architecture/content-labels.md` и `docs/architecture/variant-acceptance.md`.
