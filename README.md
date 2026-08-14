# MusicArk

MusicArk — desktop-приложение для работы с личной музыкальной коллекцией. Текущий перезапуск проекта ограничен одним сценарием: вход по токену Яндекс Музыки и просмотр списка «Мне нравится».

**Русский** · [English](README_EN.md)

## О проекте

Проект перезапущен с минимального вертикального среза вместо развития прежнего набора несвязанных функций. Существующие модули загрузок, синхронизации, метаданных и локальной библиотеки остаются в репозитории как legacy-код, но не входят в поддерживаемый MVP-сценарий.

Текущий поток:

```text
Flutter UI
  -> token in child-process environment
  -> Python mvp_bridge
  -> YandexMusicProvider
  -> yandex-music
  -> liked tracks
  -> Flutter list
```

## Статус проекта

Стадия: **MVP restart, v0.1.0**.

В текущей ветке реализованы UI входа, проверка токена и чтение «Мне нравится». Автоматические тесты добавлены, но реальный сетевой сценарий с пользовательским токеном и Windows release-сборка должны быть пройдены вручную на машине разработчика.

## Возможности

- ввод токена Яндекс Музыки непосредственно в приложении;
- проверка токена через существующий `YandexMusicProvider`;
- получение текущего списка «Мне нравится» без записи в SQLite;
- отображение названия, исполнителей и альбома;
- обновление списка без повторного ввода токена в рамках текущего запуска;
- выход с очисткой токена из состояния UI;
- передача токена Python-процессу через environment, а не через аргументы командной строки;
- поиск корня репозитория из debug/release-каталога и поддержка `MUSICARK_REPO_ROOT`;
- поиск Python через `python`, `py -3` и `MUSICARK_PYTHON`.

## Быстрый старт

### 1. Клонирование

```powershell
git clone https://github.com/Regstar2/music-ark.git
cd music-ark
```

### 2. Python-окружение

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

Если PowerShell запрещает активацию скрипта, можно выполнить команды через Python из venv напрямую:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-yandex.txt
$env:MUSICARK_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
```

### 3. Flutter-зависимости

```powershell
cd ui\musicark_ui
flutter doctor
flutter config --enable-windows-desktop
flutter pub get
```

### 4. Запуск для тестирования

```powershell
flutter run -d windows
```

В открывшемся окне:

1. вставьте токен Яндекс Музыки;
2. нажмите **«Войти»**;
3. проверьте имя аккаунта;
4. проверьте список **«Мне нравится»**;
5. нажмите кнопку обновления и убедитесь, что список загружается повторно;
6. нажмите **«Выйти»** и убедитесь, что приложение возвращается к форме входа.

## Требования

- Windows desktop;
- Python `>=3.10` — ограничение из `pyproject.toml`;
- Flutter SDK с Dart, удовлетворяющим `^3.11.5` из `ui/musicark_ui/pubspec.yaml`;
- стандартный Windows C++ toolchain, который требует Flutter для desktop-сборки;
- доступ к Яндекс Музыке и действующий токен;
- интернет-соединение для реального входа и чтения библиотеки.

Проверьте среду перед запуском:

```powershell
python --version
flutter --version
flutter doctor -v
```

## Установка

Для разработки используется editable-установка Python-пакета:

```powershell
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

Flutter-пакеты устанавливаются отдельно:

```powershell
cd ui\musicark_ui
flutter pub get
```

Приложение пока не поставляется как автономный installer.

## Использование

### Вход

Токен вводится в поле приложения. После успешной проверки MusicArk запрашивает список лайков через `YandexMusicProvider.list_tracks()`.

### Обновление

Кнопка обновления повторно получает «Мне нравится» с тем же токеном, который хранится только в памяти текущего процесса Flutter.

### Выход

Кнопка **«Выйти»** удаляет токен из состояния текущего UI и возвращает форму входа.

## Конфигурация

Поддерживаются две переменные среды для среды разработки:

| Переменная | Назначение |
|---|---|
| `MUSICARK_PYTHON` | полный путь к Python, если `python` или `py -3` недоступны через PATH |
| `MUSICARK_REPO_ROOT` | полный путь к корню репозитория, если автоматический поиск не подходит |

Пример:

```powershell
$env:MUSICARK_PYTHON = "C:\Path\To\python.exe"
$env:MUSICARK_REPO_ROOT = "C:\Base\music-ark"
flutter run -d windows
```

Токен не требуется записывать в `.env`, `local.properties` или README для нового MVP-сценария.

## Приватность

MVP не сохраняет введённый токен в SQLite или конфигурационный файл. Flutter передаёт токен дочернему Python-процессу через переменную среды `YANDEX_MUSIC_TOKEN`.

Python-провайдер по-прежнему поддерживает legacy fallback к `YANDEX_MUSIC_TOKEN` процесса и `local.properties`, но новый UI не записывает токен в эти места.

Не публикуйте токен в Git, issue, логах или скриншотах.

## Диагностика

### Python не найден

Проверьте:

```powershell
python --version
py -3 --version
```

Если Python установлен, но не находится автоматически:

```powershell
$env:MUSICARK_PYTHON = "C:\Path\To\python.exe"
```

### Корень репозитория не найден

Запускайте приложение из checkout репозитория либо задайте:

```powershell
$env:MUSICARK_REPO_ROOT = "C:\Path\To\music-ark"
```

### Яндекс отклоняет токен

Введите новый действующий токен. MusicArk не исправляет и не обновляет токен автоматически.

### Flutter не видит Windows

Проверьте:

```powershell
flutter config --enable-windows-desktop
flutter doctor -v
flutter devices
```

## Сборка

Из `ui\musicark_ui`:

```powershell
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build windows --release
```

Ожидаемый исполняемый файл по текущему `windows/CMakeLists.txt`:

```text
ui\musicark_ui\build\windows\x64\runner\Release\musicark_ui.exe
```

Запуск собранной версии:

```powershell
.\build\windows\x64\runner\Release\musicark_ui.exe
```

Release-сборка пока **не автономна**: ей нужен доступ к checkout репозитория и установленному Python с зависимостями MusicArk.

## Тестирование

### Python

Из корня репозитория:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -p "test_*.py" -v
```

Если venv не активирован:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

### Flutter

```powershell
cd ui\musicark_ui
flutter analyze
flutter test
```

### Полная ручная проверка MVP

После автоматических тестов:

```powershell
flutter run -d windows
```

Пройдите сценарий из [`docs/testing/manual-test-plan.md`](docs/testing/manual-test-plan.md).

## Документация

- [Идея проекта](docs/product/idea.md)
- [Scope MVP](docs/product/mvp-scope.md)
- [Roadmap](docs/product/roadmap.md)
- [Технологический стек](docs/architecture/tech-stack.md)
- [Архитектура](docs/architecture/architecture.md)
- [Индекс версий](docs/versions/versions-index.md)
- [v0.1.0](docs/versions/v0.1.0.md)
- [Ручной тест-план](docs/testing/manual-test-plan.md)
- [Release checklist](docs/release/release-checklist.md)
- [CHANGELOG](CHANGELOG.md)

## Ограничения

- токен пока вводится вручную;
- токен не сохраняется между запусками;
- release-сборка не включает Python runtime и Python-зависимости;
- UI поддерживает только сценарий Яндекс Музыки → «Мне нравится»;
- legacy-модули загрузки, sync, metadata и local library не считаются частью текущего MVP;
- реальный сетевой сценарий зависит от неофициальной библиотеки `yandex-music`;
- сборка и реальный вход должны быть подтверждены на Windows-машине разработчика после получения изменений.

## Лицензия

Лицензия проекта пока не выбрана, и файла `LICENSE` в репозитории нет. До выбора лицензии не следует считать код разрешённым для распространения или повторного использования.
