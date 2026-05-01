# platform-bridge

## Назначение

Слой связи между UI и Python-ядром.

## Отвечает за

- скрывать различия Windows и Android;
- передавать команды из Flutter UI в Python core;
- возвращать результаты и ошибки;
- не содержать бизнес-логику;
- не принимать решений о синхронизации;

## Связи

- [[platform-bridge]] -> [[ui]]
- [[platform-bridge]] -> [[core]]
- [[platform-bridge]] -> [[platforms]]
- [[platform-bridge]] -> [[storage]]

## Примечания

Windows: Flutter -> Python sidecar -> Python core. Android: Flutter -> Kotlin bridge -> embedded Python -> Python core.

## Команды (оформление v1.0)

Подкоманда `action`:

- общие флаги: `--name …`, необязательно `--path`, необязательно `--payload '<JSON>'` для действий с аргументами;
- snapshot дополняется `mvp_hints` (`schema_version`, `latest_sync_plan_id`).
- действия MVP (подробности в коде `src/musicark/platform_bridge.py`):

| `--name` | Назначение |
|----------|-------------|
| `metadata_get` / `metadata_update` / `metadata_bulk_update` | [[metadata-engine]] |
| `yandex_auth_check` | проверка токена [[yandex-music-provider]] (без записи коллекции) |
| `download_enqueue_run` | одна задача `yandex_download` через [[download-system]] (`confirm`, `external_id` / `track_id`, опц. папка/качество) |
| `sync_execute_safe` | v1.0 «безопасное» исполнение сохранённого плана (`confirm`, опц. `plan_id`; см. [[sync-executor]]) |
| классический поток сканирования и планирования | `scan_yandex`, `scan_local`, `match_run`, `sync_plan` |
| `experimental_yandex_upload` | v0.11 пробник (обычно `not_supported`), при включённом флаге |
