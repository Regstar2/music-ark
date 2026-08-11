# Ручной тест-план v0.2.0

## Предусловия

- Windows;
- Python/Flutter настроены по README;
- ветка `agent/v0.2-persistent-library`;
- зависимости переустановлены через `python -m pip install -e .`;
- есть действующий Yandex Music token.

## 0. Автоматические проверки

```powershell
cd C:\Base\projects\MusicArk
.\.venv\Scripts\Activate.ps1
python -c "import keyring; print(keyring.get_keyring())"
python -c "import musicark.mvp_bridge; print('MVP bridge import OK')"
python -m unittest discover -s tests -p "test_*.py" -v

cd .\ui\musicark_ui
flutter analyze
flutter test
```

Ожидается отсутствие errors и успешное завершение test suites.

## 1. Чистый первый запуск

Предусловие: пользователь вышел из MusicArk либо credential/cache ещё отсутствуют.

```powershell
flutter run -d windows
```

Ожидается форма token.

## 2. Пустой/неверный token

- пустой token не должен запускать provider request;
- неверный token должен дать понятную auth error;
- приложение остаётся на login form.

## 3. Реальный первый вход

1. Ввести рабочий token.
2. Войти.
3. Проверить account name.
4. Сверить несколько Liked tracks.
5. Проверить source/time indicators.

Ожидается network snapshot и сохранение secure session.

## 4. Search

Проверить запросы по:

- части title;
- artist;
- album;
- строке без совпадений.

Ожидается корректный filtered count и отсутствие изменения исходного cache.

## 5. Sort

Проверить:

- порядок Яндекса;
- title;
- artist.

## 6. Повторный запуск

1. Закрыть окно без logout.
2. Снова выполнить `flutter run -d windows`.

Ожидается:

- token form не показывается;
- cached library доступна автоматически;
- затем выполняется network refresh.

## 7. Offline/cache

1. После успешного cache отключить сеть.
2. Перезапустить MusicArk.

Ожидается:

- cached tracks остаются видимыми;
- показывается refresh/network error;
- cache не очищается.

## 8. Добавление membership

1. Добавить тестовый track в Yandex Liked.
2. Refresh.

Ожидается track в MusicArk и `+1` в sync diff (если других изменений нет).

## 9. Удаление membership

1. Удалить тестовый track из Yandex Liked.
2. Refresh.

Ожидается исчезновение track из MusicArk/SQLite snapshot и `-1` в diff.

## 10. Logout

1. Нажать «Выйти».
2. Закрыть приложение.
3. Запустить снова.

Ожидается:

- login form;
- cached library отсутствует;
- token требуется снова.

## 11. Credential backend диагностика

При проблеме persistence:

```powershell
python -m keyring diagnose
python -c "import keyring; print(keyring.get_keyring())"
```

Не выводить сам token.

## 12. Release build

```powershell
cd C:\Base\projects\MusicArk\ui\musicark_ui
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build windows --release

$env:MUSICARK_PYTHON = "C:\Base\projects\MusicArk\.venv\Scripts\python.exe"
$env:MUSICARK_REPO_ROOT = "C:\Base\projects\MusicArk"
.\build\windows\x64\runner\Release\musicark_ui.exe
```

Повторить сценарии 3, 6, 7 и 10.

## Что прикладывать к ошибке

- точную команду;
- stdout/stderr без token;
- текст UI error;
- `python --version`;
- `flutter --version`;
- `flutter doctor -v`;
- вывод backend class из `keyring.get_keyring()`;
- debug/release distinction.

Token никогда не прикладывать.
