# Архитектура

## v0.2.0 Persistent Library

```text
Flutter UI
    |
    | first sign-in token via child-process environment
    v
musicark.mvp_bridge
    |
    v
PersistentLibraryService
    |                         \
    v                          v
SystemCredentialStore       LikedCacheRepository
    |                          |
Windows Credential Locker     SQLite snapshot
    |
    +---- saved token ----+
                          |
                          v
                  YandexMusicProvider
                          |
                          v
                    yandex-music
```

## UI

`ui/musicark_ui/lib/main.dart`

Отвечает за:

- форму первого входа;
- cache-first bootstrap;
- автоматический refresh сохранённой сессии;
- loading/error states без уничтожения cached списка;
- поиск и сортировку;
- logout.

UI не хранит token после первого sign-in.

## Process bridge

`src/musicark/mvp_bridge.py`

Стабильные действия v0.2:

- `bootstrap` — только saved-session metadata + cache, без сети;
- `login` — token из environment, auth, network snapshot, secure save;
- `refresh` — token из credential store, network snapshot replacement;
- `cached` — чтение snapshot без сети;
- `logout` — удаление credential и cache.

Token никогда не передаётся через argv.

## PersistentLibraryService

`src/musicark/persistent_library.py`

Orchestration-слой между credentials, provider и cache. Он задаёт порядок операций и гарантирует, что неуспешный network refresh не очищает последний рабочий snapshot.

## Credentials

`src/musicark/credentials.py`

`SystemCredentialStore` использует Python `keyring`. На Windows целевой backend — Windows Credential Locker.

Идентификаторы:

- service: `MusicArk`;
- username: `yandex_music_token`.

Token не хранится в SQLite/config.

## Cache

`src/musicark/storage/liked_cache.py`

Используются отдельные таблицы membership/snapshot:

- `provider_collection_snapshots`;
- `provider_collection_items`.

Snapshot заменяется в одной SQLite transaction. Это важно: `provider_tracks` legacy-схемы умеет upsert, но сама по себе не описывает удаление трека из конкретной коллекции.

Schema migration: `1.1.0`.

## Provider

`src/musicark/providers/yandex_music_provider.py`

Provider теперь может получить token явно через constructor. Legacy fallback через environment/local.properties сохранён для старых CLI flows.

## Ошибки

Bridge нормализует provider/storage/credential ошибки в стабильные codes. Flutter может показывать cached library одновременно с ошибкой refresh.

## Legacy boundary

Download, matching, sync, metadata и local-library подсистемы не подключаются обратно к UI в v0.2.0.
