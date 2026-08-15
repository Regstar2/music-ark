# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.7.0 — Download.**

MusicArk — Windows desktop-приложение, которое связывает библиотеку Яндекс Музыки с локальной музыкальной коллекцией. v0.5 устанавливает identity, v0.5.1 отдельно проверяет вариант записи, v0.6 выводит Library Coverage / Missing Tracks, а v0.7 замыкает пользовательский цикл безопасной загрузкой явно отмеченных отсутствующих треков.

## Основной цикл

```text
Yandex Library
      ↓
Local Library
      ↓
Identity Matching
      ↓
Missing Tracks / Coverage
      ↓
Wanted
      ↓
Download Queue
      ↓
authorized Yandex download
      ↓
normal Local Library index
      ↓
exact provider/local identity
      ↓
Coverage = covered
```

Обычный кандидат v0.7 определяется строго:

```text
coverage_status = missing
AND user_action = wanted
```

`needs_review`, `conflict`, `not_analyzed`, уже `covered` треки и `MATCHED + DIFFERENT_VERSION` автоматически не загружаются.

## Яндекс Музыка

- вход по Yandex Music OAuth token через системный credential store;
- cache-first сессия, «Мне нравится», плейлисты и offline cache;
- одна provider identity `(yandex_music, external_id)` независимо от количества memberships;
- v0.7 использует только существующий authenticated Yandex Music download workflow и возможности текущего аккаунта/API.

MusicArk v0.7 **не** реализует YouTube ripping, VK scraping, торрент-поиск, pirate indexes, DRM circumvention, subscription/access bypass или автоматический поиск альтернативного источника.

## Local Library

- несколько roots и native Windows folder picker;
- structured title/artists/album/duration/codec и технические поля;
- incremental scan, SQL search/sort/pagination;
- существующая музыка остаётся read-only: MusicArk не переименовывает, не перемещает, не удаляет и не редактирует её tags.

Downloaded-файл является исключением только в смысле создания **нового** файла. После загрузки он проходит тот же `LocalMetadataReader` и `LocalLibraryStorageRepository`, что и обычный v0.4 scan, и получает настоящий `library_root_id` / `normalized_path`.

## Identity / Variant / Coverage — независимые слои

Identity Matching v0.5 отвечает: это тот же трек или нет (`MATCHED / CONFLICT / UNMATCHED`). Variant v0.5.1 отвечает: та же ли это запись/версия (`SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED`). Coverage v0.6 выводит:

```text
covered       — актуальный accepted local identity
missing       — authoritative UNMATCHED без accepted local link
needs_review  — conflict/stale/invalid accepted link
not_analyzed  — matching отсутствует или устарел
```

После exact provider download MusicArk знает source identity и не запускает fuzzy matching для её угадывания: создаётся accepted `exact_id` link. При этом v0.7 **не создаёт ложный `Variant = SAME`** — Variant остаётся независимым результатом анализа.

## v0.7 Download

### Destination

Пользователь выбирает папку через существующий Windows folder picker. Она становится Local Library root либо используется существующий parent root. Управляемая папка по умолчанию:

```text
<Local Library root>\MusicArk\
```

Выбранный root хранится persistent в SQLite. Каждая задача также snapshot-ит destination/root при enqueue, поэтому последующая смена default target не перемещает уже поставленные задачи.

Имена Windows-safe и содержат provider ID, например:

```text
Artist - Title [yandex_123456].mp3
```

### Queue

Пользовательские состояния:

```text
queued
running
completed
failed
cancelled
skipped
```

`paused` не показывается, потому что настоящий pause/resume не реализован. Worker v0.7 намеренно последовательный (`max concurrency = 1`) ради предсказуемой SQLite/файловой семантики.

Очередь хранится в SQLite. Persisted `running` после crash/restart восстанавливается в retryable `failed / interrupted`. Повторный enqueue одной активной Yandex identity не создаёт вторую задачу.

### Streaming / progress / cancel

Yandex HTTP response пишется streaming-способом, без audio blobs в памяти/SQLite:

```text
final.mp3.part
      ↓ success
final.mp3
```

Если известен `Content-Length`, UI показывает downloaded bytes / total bytes / percentage. Если размер неизвестен — indeterminate progress. SQLite progress writes throttled, а не выполняются на каждый 64 KiB chunk.

Running cancellation cooperative: worker проверяет persisted `cancel_requested` между chunks. `.part` удаляется, final-файл не появляется. HTTP Range resume в v0.7 не заявляется; Retry начинает загрузку заново.

### Post-download quality gate

`completed` разрешён только после всей цепочки:

```text
network complete
  + non-empty atomic final file
  + LocalMetadataReader can parse audio
  + Local Library indexing with non-NULL root_id
  + exact provider/local link
  + Coverage refresh == covered
```

Если любой обязательный шаг не выполнен, задача не становится `completed`.

## Credentials / privacy

Production Download получает token из `SystemCredentialStore` и явно передаёт его provider-адаптеру. Token и временный direct download URL запрещены в argv, `download_tasks`, `raw_payload_json`, SQLite, filenames, UI details и audit log.

Local Library data не отправляется во внешние сервисы, кроме минимального запроса выбранному provider для конкретного provider track.

## Reference audio ≠ Download Library

v0.5.1 exact-reference cache остаётся отдельным:

```text
.musicark/downloads/yandex/yandex_<id>.<ext>
```

Он нужен для Variant verification, не является пользовательской Local Library, не создаёт coverage и не используется как destination для wanted downloads.

## UI

Основная навигация:

```text
MusicArk
├── Яндекс Музыка
├── Локальная библиотека
├── Сопоставление
├── Недостающие
└── Загрузки
```

На Missing row после решения **Нужен** появляется действие **В загрузки**. Страница «Загрузки» показывает summary, filters, target folder, очередь, real/indeterminate progress, Retry, Cancel и очистку completed history. Очистка history никогда не удаляет скачанные аудиофайлы.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage user actions
1.7.0 — Download queue/progress/settings
```

v1.7 расширяет существующую `download_tasks`, а не создаёт `download_tasks_v2`, и добавляет persistent download settings. Forward migration сохраняет Yandex cache, Local Library, matching/manual/conflict state, Variant results, wanted/ignored decisions и legacy download rows.

## Запуск для разработки на Windows

```powershell
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
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download
v0.8   — Sync
```

См. `docs/versions/v0.7.0.md`, `docs/architecture/architecture.md` и `docs/testing/manual-test-plan.md`.
