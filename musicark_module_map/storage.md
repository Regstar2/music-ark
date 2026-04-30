# storage

## Назначение

Слой хранения данных приложения.

## Отвечает за

- хранить SQLite-базу;
- хранить настройки;
- хранить снимки коллекции;
- хранить связи между сущностями;
- хранить [[download-task]];
- хранить историю действий;
- хранить raw_data провайдеров;

## Связи

- [[storage]] -> [[core]]
- [[storage]] -> [[providers]]
- [[storage]] -> [[download-system]]
- [[storage]] -> [[canonical-library]]
- [[storage]] -> [[local-archive]]
- [[storage]] -> [[history-audit-log]]
- [[storage]] -> [[ui]]

## Правила

В базе не должно быть `yandex_tracks` как главной таблицы. Нужны универсальные provider_tracks, track_sources, local_audio_files, canonical_tracks, track_links.

## Реализация v0.1

`v0.1-core-foundation` добавляет первичный слой хранения в `src/musicark/storage/`:

- инициализация SQLite схемы (`app_metadata`, `audit_log`);
- минимальный репозиторий для записи событий в [[history-audit-log]];
- отсутствие зависимости от provider-specific таблиц.

## Расширение v0.2

`v0.2-provider-architecture` расширяет [[storage]]:

- таблица `providers` для сохранения capabilities и metadata провайдеров;
- таблица `track_sources` для универсальных источников треков;
- `ProviderStorageRepository` для upsert-операций metadata.
