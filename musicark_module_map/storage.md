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

## Расширение v0.3

`v0.3-yandex-scan` добавляет provider scan-хранилище:

- `provider_tracks` для нормализованных provider track payload;
- `provider_playlists` для нормализованных provider playlist payload;
- `provider_raw_responses` для безопасного raw-представления scan ответа;
- upsert и insert методы в `ProviderStorageRepository`.

## Расширение v0.4

`v0.4-local-library` добавляет:

- таблицу `local_audio_files`;
- `LocalLibraryStorageRepository` для upsert/list/stats локальных файлов;
- связь локального скана с `track_sources` (`provider_id=local_library`).

## Расширение v0.5

`v0.5-download-system` добавляет:

- таблицу `download_tasks`;
- `DownloadStorageRepository` для очереди download-task;
- связь `download-task -> local_audio_file` через `result_local_file_id`.

## Расширение v0.7

`v0.7-matching` добавляет таблицы canonical-library:

- `tracks`;
- `track_links`;
- `match_conflicts`.

## Расширение v0.8

`v0.8-sync-planner` добавляет:

- `sync_plans`;
- `sync_operations`;
- `SyncStorageRepository` для сохранения/чтения/отмены SyncPlan.

## Расширение v1.0

[[v1.0-stable-desktop-mvp]]:

- `musicark/storage/migrations.py` — упорядоченные только вперёд миграции по ключу `app_metadata.schema_version` (стартует с seed `0.1.0` для существующих БД без ключа).
- Первая миграция `1.0.0` создаёт индекс `idx_audit_log_created_at` на [[history-audit-log]] для производительности и отчётов.
- `initialize_database()` после DDL выполняет `ensure_schema_version_seed` и `migrate_schema`.
