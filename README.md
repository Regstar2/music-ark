# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.3.0 — Yandex Library / Playlists.**

MusicArk — desktop-first приложение для сохранения и дальнейшей синхронизации личной музыкальной библиотеки. На этапе v0.3 основной рабочий provider — Яндекс Музыка.

## Что работает в v0.3

- одноразовый вход по Yandex Music OAuth token с сохранением токена в системном credential store;
- cache-first запуск без повторного ввода токена;
- «Мне нравится» с refresh, offline fallback, поиском и сортировкой;
- список пользовательских плейлистов Яндекс Музыки;
- открытие плейлиста и просмотр его треков в исходном Yandex-порядке;
- локальный SQLite snapshot playlist metadata + membership + position;
- lazy refresh содержимого плейлиста при открытии;
- «Обновить библиотеку» для account + Likes + playlist metadata без полного N-playlist сканирования;
- удаление stale playlist cache после подтверждённого полного refresh;
- offline-доступ к ранее загруженным playlist snapshots;
- logout очищает credential и provider cache.

## Архитектура v0.3

```text
Flutter desktop UI
        ↓
musicark.mvp_bridge
        ↓
YandexLibraryService
   ↓             ↓
Yandex provider  SQLite collection cache
        ↓
   yandex-music
```

Flutter не знает детали `yandex-music` и SQLite. Объекты сторонней библиотеки остаются внутри provider boundary.

SQLite использует универсальные коллекции:

- `yandex_music / liked`;
- `yandex_music / playlist:<external_id>`.

Токен не записывается в SQLite и не передаётся через argv. UI передаёт токен bridge только через environment дочернего процесса при login, после чего используется системное хранилище учётных данных.

## Запуск для разработки на Windows

Из корня репозитория:

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

Существующая `.musicark/musicark.db` удалять не нужно: `initialize_database()` применяет forward-only migration `1.2.0` автоматически.

## Проверка реального Yandex

Unit/widget tests не требуют реального аккаунта. Перед закрытием v0.3 вручную на Windows нужно подтвердить: сохранённую сессию, реальные playlists, открытие playlist tracks, refresh, restart/offline cache и logout. Не храните OAuth token в Git.

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

Standalone packaging/installer не является приоритетом текущего этапа.

Подробности: `docs/versions/v0.3.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`.
