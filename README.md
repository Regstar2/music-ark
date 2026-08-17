# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.8.2 — Local Metadata Editor & Yandex Metadata Import.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. Local Library, Identity Matching, Variant, Coverage, Download и Controlled Sync остаются отдельными слоями. v0.8.2 добавляет отдельный **явный** контур редактирования metadata уже существующих локальных файлов.

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

Для файлов с плохими тегами появился дополнительный ручной workflow:

```text
Local Library
  → Редактировать метаданные
  → локальная правка
      или
    поиск Yandex Track → Compare
  → Применить метаданные
      или
    Применить и связать
  → transactional MP3 write
  → single-file reindex + SHA-256
  → targeted Matching refresh
  → Coverage/UI refresh
```

## Metadata и Identity — разные сущности

**«Применить метаданные»** меняет только выбранные непустые поля/обложку локального MP3, после чего запускает обычный Matching. Даже 100% similarity сама по себе не становится подтверждённой identity.

**«Применить и связать»** — отдельное явное подтверждение пользователя. Оно создаёт:

```text
provider   = yandex_music
external   = <Yandex Track ID>
local file = <Local File ID>
method     = exact_id
confidence = 1.0
reason     = user_confirmed
```

При таком bind MusicArk также пишет доверенный provenance в ID3 TXXX. Это позволяет восстановить provider identity после удаления БД, переименования или переноса файла. Зарезервированные provenance-теги нельзя редактировать через обычный раздел «Все теги».

## Безопасность изменения файлов

Обычные:

- Scan;
- Matching;
- Coverage;
- Sync;

**не изменяют пользовательские аудиофайлы**.

Существующий файл изменяется только после явного действия в Metadata Editor. Для MP3 используется pipeline:

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

До atomic replace оригинал остаётся неизменным. Audio stream не транскодируется. Basic Save меняет только запрошенные frames; неизвестные/custom tags сохраняются.

## Artwork

Local Library показывает thumbnail каждого трека. Приоритет:

1. embedded artwork;
2. уже cached Yandex artwork для подтверждённой identity;
3. placeholder.

Список библиотеки не делает Yandex request для каждой строки и не передаёт большие base64-картинки во Flutter: UI получает cache path и декодирует thumbnail лениво.

## Yandex metadata import

Поиск и получение полного Track DTO выполняются только в Python/backend через существующую Yandex provider/auth границу. Flutter не получает Yandex token, Authorization header, cookies, signed/direct media URL.

Compare позволяет выборочно импортировать доступные поля и artwork. Пустое поле Yandex не стирает локальное значение автоматически.

## Форматы

Архитектура использует format adapters. В v0.8.2 полноценная безопасная запись реализована для **MP3/ID3**. Другие аудиоформаты пока доступны редактору только для просмотра до появления их transactional adapters.

## Controlled Sync

Sync остаётся read-only planner/executor поверх существующих слоёв и не является двунаправленным filesystem mirror. Его стандартный Apply по-прежнему даёт:

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
```

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
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download + Local Playback
v0.8.0 — Controlled Sync
v0.8.1 — Rich Yandex download metadata/provenance
v0.8.2 — Local Metadata Editor / Yandex Metadata Import
next   — stabilization / TBD
```

См. `docs/versions/v0.8.2.md` и `docs/architecture/metadata-editor.md`.
