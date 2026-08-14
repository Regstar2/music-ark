# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.4.0 — Local Library.**

MusicArk — Windows desktop-приложение, которое объединяет библиотеку Яндекс Музыки и локальную музыкальную коллекцию пользователя. v0.4 добавляет вторую сторону продукта: индексирование папок с музыкой с сохранением metadata в общей SQLite БД.

## Что работает в v0.4

### Яндекс Музыка

- безопасный вход по Yandex Music OAuth token через системный credential store;
- cache-first восстановление сессии;
- «Мне нравится»;
- пользовательские плейлисты и их треки;
- поиск, сортировка, refresh и offline cache.

### Local Library

- отдельный раздел **«Локальная библиотека»**;
- native Windows folder picker;
- несколько music roots;
- рекурсивный scan MP3/FLAC/M4A/MP4/AAC/OGG/Opus/WAV, которые распознаёт metadata stack;
- чтение title, artists, album, album artist, duration и технических полей через `mutagen`;
- fallback title из имени файла при отсутствии tags;
- incremental reconciliation: new / changed / unchanged / removed;
- быстрый unchanged-check по normalized path + file size + mtime_ns без повторного SHA-256 всей коллекции;
- SQLite search, sorting и `limit`/`offset` для больших библиотек;
- detail dialog с metadata и абсолютным путём;
- per-file errors не останавливают весь scan;
- symlink/reparse directories не обходятся рекурсивно.

> **MusicArk v0.4 не изменяет и не удаляет локальные музыкальные файлы.** Удаление папки из MusicArk удаляет только записи индекса. v0.4 не переименовывает файлы, не меняет tags, не переносит, не конвертирует и не удаляет музыку.

## Local Library: основной сценарий

```text
Локальная библиотека
        ↓
Добавить папку
        ↓
выбрать C:\Music
        ↓
Сканировать
        ↓
metadata → SQLite
        ↓
поиск / сортировка / просмотр
```

При следующем запуске roots и индекс остаются в `.musicark/musicark.db`. Повторный scan перечитывает metadata только у новых или изменённых файлов и удаляет из индекса записи файлов, которые действительно исчезли из полностью доступной source folder.

## Архитектура v0.4

```text
Flutter desktop
   ├─ Yandex UI → musicark.mvp_bridge → YandexLibraryService → Yandex provider/cache
   └─ Local UI  → musicark.mvp_bridge → LocalLibraryService
                                      → LocalLibraryScanner
                                      → LocalMetadataReader
                                      → LocalLibraryStorageRepository
                                      → shared SQLite
```

Local Library не является Yandex provider. Пути добавляемых folders передаются bridge через environment, а не через shell-string/argv. Scanner использует `Path`/`os.walk` и не выполняет destructive filesystem operations.

SQLite forward migration v0.4: `1.3.0`. Существующие Yandex collection snapshots не очищаются.

## Запуск для разработки на Windows

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

Не удаляйте существующую `.musicark/musicark.db`: `initialize_database()` автоматически применяет forward migration `1.3.0`. Сохранённый Yandex token также удалять не требуется.

## Ручная Windows-проверка v0.4

Используйте отдельную тестовую папку, например `C:\MusicArk-Test`, а не основную коллекцию. Проверить: add folder → scan → restart → add/change/delete file → rescan, затем убедиться, что Yandex Likes/Playlists и сохранённая сессия продолжают работать.

## Roadmap

```text
v0.1 — Yandex Likes MVP
v0.2 — Persistent Library
v0.3 — Yandex Library / Playlists
v0.4 — Local Library
v0.5 — Matching
v0.6 — Missing Tracks
v0.7 — Download
v0.8 — Sync
```

Standalone packaging/installer остаётся второстепенной инфраструктурной задачей.

Подробности: `docs/versions/v0.4.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`.
