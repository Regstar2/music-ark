<div align="center">

# MusicArk

Настольный проект для сохранения и восстановления личной музыкальной коллекции. Python-ядро индексирует локальные файлы и данные провайдеров, хранит состояние в SQLite, планирует синхронизацию и предоставляет CLI и Flutter-интерфейс для Windows.

**Русский** · [English](README_EN.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/UI-Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![SQLite](https://img.shields.io/badge/storage-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/status-desktop%20MVP-6F42C1?style=for-the-badge)

[Быстрый старт](#быстрый-старт) ·
[Команды](#команды) ·
[Архитектура](#архитектура) ·
[Ограничения](#ограничения)

</div>

---

## О проекте

MusicArk создаёт локальный каталог музыкальной коллекции и связывает записи из разных источников. Проект объединяет Python-пакет, SQLite-хранилище, провайдер Яндекс Музыки, очередь загрузок, matching engine, sync planner, JSON bridge и Flutter-приложение.

Основной принцип — сначала построить и сохранить план, затем выполнять только явно разрешённые операции. Текущий safe executor обрабатывает ограниченный набор задач загрузки и не превращает экспериментальный код восстановления в автоматическую запись на удалённый сервис.

## Статус проекта

| Область | Статус |
|---|---|
| Python core и CLI | Реализованы |
| SQLite schema и forward migrations | Реализованы |
| Сканирование локальной коллекции | Реализовано |
| Чтение данных Яндекс Музыки | Реализовано через отдельную зависимость |
| Загрузка треков из Яндекс Музыки | Реализована |
| Matching и sync planning | Реализованы |
| Safe sync execution | Ограничено задачами `CREATE_DOWNLOAD_TASK` для Yandex download |
| Flutter Windows UI | Desktop MVP |
| Загрузка треков обратно в Яндекс Музыку | Не поддерживается используемой библиотекой |

## Возможности

- инициализация SQLite и последовательные миграции схемы;
- аудит операций;
- сканирование лайков и плейлистов Яндекс Музыки;
- рекурсивное сканирование локальных аудиофайлов;
- индексирование файлов, хэшей и основных метаданных;
- универсальная очередь загрузок с состояниями задач;
- одиночная и пакетная загрузка треков из Яндекс Музыки;
- matching engine с canonical tracks, связями и очередью конфликтов;
- сохранение dry-run планов синхронизации;
- безопасное выполнение поддерживаемых операций из сохранённого плана;
- редактирование метаданных через Mutagen с локальными резервными копиями;
- CLI `musicark`, JSON bridge `musicark-bridge` и Flutter dashboard.

## Быстрый старт

Создайте окружение и установите Python-пакет:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install -r requirements-yandex.txt
```

Инициализируйте базу и проверьте CLI:

```powershell
musicark db-init
musicark health-check
```

Запустите unit-тесты:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Flutter UI:

```powershell
cd ui\musicark_ui
flutter pub get
flutter run -d windows
```

## Требования

- Python 3.10 или новее;
- Windows для текущего Flutter desktop-клиента;
- Flutter/Dart для запуска UI;
- доступ к Яндекс Музыке и действующая авторизация для provider-команд;
- локальное место для SQLite, скачанных треков и резервных копий метаданных.

## Использование

### Локальная коллекция

```powershell
musicark local scan --path "D:\Music"
musicark local stats
musicark local list
```

### Яндекс Музыка

```powershell
musicark yandex auth-check
musicark yandex scan-likes
musicark yandex scan-playlists
musicark yandex download-track --id "<track_id>" --quality best
```

### Сопоставление и синхронизация

```powershell
musicark match run
musicark match list-conflicts
musicark sync plan --dry-run
musicark sync execute-safe --confirm
```

Перед выполнением безопасной синхронизации проверьте сохранённый план. Команда выполняет только поддерживаемые типы операций и требует явного `--confirm`.

## Конфигурация

Основная конфигурация хранится локально в `.musicark/config.json`. Данные SQLite, загруженные файлы и резервные копии метаданных также остаются в локальной рабочей области проекта.

Экспериментальный флаг Yandex upload можно включить в настройках Flutter или через `MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD=1`, но это запускает только защищённый probe: используемая библиотека не предоставляет API загрузки, поэтому обычный результат — `not_supported`.

Не сохраняйте токены провайдера в отслеживаемых Git-файлах.

## Команды

| Группа | Примеры |
|---|---|
| Состояние | `musicark health-check`, `musicark config-show` |
| База данных | `musicark db-init` |
| Яндекс Музыка | `musicark yandex auth-check`, `scan-likes`, `scan-playlists`, `download-track` |
| Локальная коллекция | `musicark local scan`, `local list`, `local stats` |
| Загрузки | `musicark download queue`, `download run` |
| Сопоставление | `musicark match run`, `match list-conflicts`, `match accept` |
| Синхронизация | `musicark sync plan --dry-run`, `plan-show`, `plan-cancel`, `execute-safe --confirm` |
| Bridge | `musicark-bridge snapshot`, `musicark-bridge action --name <action>` |

Полный набор аргументов следует проверять через `--help` текущей версии CLI.

## Архитектура

```text
Flutter Windows UI
        │ JSON subprocess bridge
        ▼
musicark-bridge
        │
        ▼
Python application services
├── providers
├── local library
├── download queue
├── matching engine
├── sync planner / safe executor
├── metadata editor
└── audit log
        │
        ▼
SQLite + local music files
```

Provider-specific DTO и API изолированы от основной модели. Опасные действия требуют явного подтверждения, а планирование отделено от выполнения.

## Приватность

- каталог коллекции и служебные данные хранятся в локальной SQLite;
- локальные файлы обрабатываются на устройстве;
- запросы к Яндекс Музыке выполняются только при использовании соответствующего provider-а;
- резервные копии изменённых тегов сохраняются в `.musicark/metadata_backups`;
- проект не содержит отдельного облачного backend-а MusicArk.

Токен Яндекс Музыки даёт доступ к аккаунту и должен храниться как секрет.

## Сборка

Установка Python-пакета в editable-режиме:

```powershell
pip install -e .
```

Запуск Flutter-клиента из исходников:

```powershell
cd ui\musicark_ui
flutter pub get
flutter run -d windows
```

## Тестирование

Локальная команда:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

GitHub Actions workflow `.github/workflows/tests.yml` запускает Python 3.12, устанавливает пакет через `pip install -e .` и выполняет unittest suite. В рамках изменения README тесты не запускались, поэтому документ не заявляет результат текущей ветки.

## Документация

| Задача | Ресурс |
|---|---|
| Метаданные Python-пакета | [pyproject.toml](pyproject.toml) |
| Исходный код ядра | [src/musicark/](src/musicark/) |
| Unit-тесты | [tests/](tests/) |
| Flutter-клиент | [ui/musicark_ui/](ui/musicark_ui/) |
| CI | [.github/workflows/tests.yml](.github/workflows/tests.yml) |
| Зависимость Яндекс Музыки | [requirements-yandex.txt](requirements-yandex.txt) |

## Ограничения

- используемый Python-клиент Яндекс Музыки не предоставляет API загрузки треков обратно в библиотеку;
- `sync execute-safe` выполняет только ограниченный тип подтверждённых download-операций;
- Flutter-клиент ориентирован на Windows и не подтверждён на других desktop-платформах;
- автоматическое создание restore-плейлиста отсутствует;
- версия Python-пакета (`0.1.0`), Flutter-приложения (`1.0.0+1`) и milestone v1.0 пока не синхронизированы;
- проект работает с личной коллекцией и требует резервной копии перед массовым изменением тегов или выполнением планов;
- условия распространения исходного кода пока не определены.

## Лицензия

В корне репозитория отсутствует файл `LICENSE`. До выбора лицензии код нельзя считать открытым для копирования, изменения или распространения. Зависимости и сторонние сервисы сохраняют собственные условия использования.
