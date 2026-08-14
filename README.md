# MusicArk

MusicArk — Windows desktop-приложение для личной музыкальной коллекции. Версия **v0.2.0 Persistent Library** развивает подтверждённый v0.1.0: после первого входа токен сохраняется в защищённом системном хранилище, библиотека «Мне нравится» кэшируется локально и доступна сразу при следующем запуске.

**Русский** · [English](README_EN.md)

## Что работает в v0.2.0

- первый вход по Yandex Music OAuth token;
- безопасное сохранение токена через Python `keyring` / Windows Credential Locker;
- автоматическое восстановление сессии после перезапуска приложения;
- SQLite snapshot списка «Мне нравится»;
- показ локального cache до завершения сетевого refresh;
- сохранение cache при сетевой ошибке;
- корректное удаление из cache треков, убранных из «Мне нравится»;
- отображение количества треков и времени последнего обновления;
- поиск по названию, исполнителю и альбому;
- сортировка по порядку Яндекса, названию или исполнителю;
- refresh с подсчётом добавленных/удалённых треков;
- logout с удалением сохранённого токена и cached library.

Legacy download/matching/sync/metadata/local-library код остаётся в репозитории, но не возвращён в поддерживаемый UI.

## Архитектура

```text
Flutter UI
  -> musicark.mvp_bridge subprocess
       -> SystemCredentialStore -> Windows Credential Locker
       -> PersistentLibraryService
            -> YandexMusicProvider -> yandex-music
            -> LikedCacheRepository -> SQLite
```

Токен при первом входе передаётся дочернему Python-процессу через environment, а не через argv. После успешного входа следующие процессы получают его из системного credential store. В SQLite токен не записывается.

## Требования

- Windows;
- Python >= 3.10;
- Flutter SDK с Windows desktop support;
- Visual Studio C++ toolchain, требуемый `flutter doctor`;
- Git;
- интернет для первого входа и обновления Яндекс Музыки.

## Полный запуск из новой PowerShell-сессии

Для текущей ветки разработки v0.2.0:

```powershell
cd C:\Base\projects\MusicArk

git fetch origin
git switch agent/v0.2-persistent-library
git pull

git status

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt

python -c "import keyring; print(keyring.get_keyring())"
python -c "import musicark.mvp_bridge; print('MVP bridge import OK')"
python -m unittest discover -s tests -p "test_*.py" -v

$env:Path = "C:\Base\tools\flutter\bin;$env:Path"
$env:MUSICARK_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path

flutter --version
flutter doctor -v
flutter config --enable-windows-desktop
flutter devices

cd .\ui\musicark_ui

flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

Если `.venv` ещё не существует:

```powershell
cd C:\Base\projects\MusicArk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
```

## Что проверить вручную

### Первый запуск

1. Открывается форма входа.
2. Ввести действующий Yandex Music token.
3. Нажать **«Войти»**.
4. Проверить имя аккаунта и несколько треков.
5. Проверить поиск и сортировку.

### Повторный запуск

Закрыть приложение и снова выполнить:

```powershell
flutter run -d windows
```

Ожидаемый результат:

- token повторно не запрашивается;
- cached «Мне нравится» появляется автоматически;
- затем MusicArk выполняет refresh;
- время последнего обновления меняется после успешного запроса.

### Offline/cache

После хотя бы одного успешного входа временно отключить сеть и снова запустить приложение.

Ожидаемый результат: cached library остаётся на экране, а ошибка refresh не удаляет список.

### Удаление из «Мне нравится»

1. Удалить тестовый трек из «Мне нравится» в Яндекс Музыке.
2. Нажать refresh в MusicArk.
3. Проверить, что трек исчез из локального snapshot и счётчик показывает удаление.

### Logout

Нажать **«Выйти»**.

Ожидаемый результат:

- token удаляется из Windows credential store;
- локальный snapshot очищается;
- появляется форма входа;
- при следующем запуске нужен token.

## Тесты

Python:

```powershell
cd C:\Base\projects\MusicArk
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -p "test_*.py" -v
```

Flutter:

```powershell
cd C:\Base\projects\MusicArk\ui\musicark_ui
flutter analyze
flutter test
```

## Release build

Из `ui\musicark_ui`:

```powershell
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build windows --release
```

Запуск:

```powershell
$env:MUSICARK_PYTHON = "C:\Base\projects\MusicArk\.venv\Scripts\python.exe"
$env:MUSICARK_REPO_ROOT = "C:\Base\projects\MusicArk"
.\build\windows\x64\runner\Release\musicark_ui.exe
```

Release-сборка v0.2.0 пока не автономна: рядом по-прежнему требуется checkout MusicArk и установленный Python environment. Автономная Windows-упаковка запланирована отдельной версией.

## Где хранятся данные

При стандартном запуске из checkout:

- настройки/SQLite: `C:\Base\projects\MusicArk\.musicark\`;
- cache «Мне нравится»: таблицы `provider_collection_snapshots` и `provider_collection_items` в MusicArk SQLite;
- Yandex token: системный credential store Windows, service `MusicArk`, username `yandex_music_token`.

Token не должен появляться в Git, README, issue, логах или SQLite.

## Диагностика

Проверка credential backend:

```powershell
python -m keyring diagnose
python -c "import keyring; print(keyring.get_keyring())"
```

Проверка Python:

```powershell
python --version
where.exe python
```

Если Flutter не найден:

```powershell
$env:Path = "C:\Base\tools\flutter\bin;$env:Path"
flutter --version
```

Если MusicArk не находит Python:

```powershell
$env:MUSICARK_PYTHON = "C:\Base\projects\MusicArk\.venv\Scripts\python.exe"
```

Если не определяется корень checkout:

```powershell
$env:MUSICARK_REPO_ROOT = "C:\Base\projects\MusicArk"
```

## Документация

- [MVP scope](docs/product/mvp-scope.md)
- [Roadmap](docs/product/roadmap.md)
- [Architecture](docs/architecture/architecture.md)
- [Versions](docs/versions/versions-index.md)
- [Manual test plan](docs/testing/manual-test-plan.md)
- [Release checklist](docs/release/release-checklist.md)
- [CHANGELOG](CHANGELOG.md)

## Ограничения v0.2.0

- поддерживается только Яндекс Музыка → «Мне нравится»;
- token всё ещё вводится вручную при первом входе;
- release build не включает Python runtime;
- playlists/download/matching/sync/local-library UI ещё не возвращены;
- интеграция с Яндекс Музыкой использует неофициальную библиотеку `yandex-music`.

## Лицензия

Файл `LICENSE` пока отсутствует.
