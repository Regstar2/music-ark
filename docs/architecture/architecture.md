# Архитектура

## Главный сценарий

```text
Flutter sign-in form
    |
    | token via child environment
    v
musicark.mvp_bridge
    |
    v
YandexMusicProvider
    |
    v
yandex-music Client
    |
    v
account / liked tracks JSON
    |
    v
Flutter state + ListView
```

## Границы

### UI

`ui/musicark_ui/lib/main.dart`

Отвечает за ввод токена, состояние сессии, loading/error states и отображение списка.

### UI-ресурсы

`ui/musicark_ui/lib/app_strings.dart`

Содержит пользовательские строки текущего MVP, чтобы transport/provider-код не формировал UI-текст.

### Process bridge

`src/musicark/mvp_bridge.py`

Имеет только два сценария: login и liked tracks. Bridge не сохраняет токен и не пишет библиотеку в SQLite.

### Provider

`src/musicark/providers/yandex_music_provider.py`

Существующий адаптер внешней библиотеки. Объекты `yandex-music` не должны выходить за эту границу.

## Секреты

Токен вводится в Flutter и передаётся только через environment дочернего процесса как `YANDEX_MUSIC_TOKEN`. Новый MVP не передаёт токен в argv и не сохраняет его на диск.

## Ошибки

Python bridge переводит известные provider exceptions в стабильные error codes. Flutter преобразует code в пользовательское сообщение и может отдельно показать техническую причину.

## Legacy

Существующие storage/download/matching/sync/metadata-модули остаются в репозитории. v0.1.0 не удаляет их и не использует в основном UI-сценарии.
