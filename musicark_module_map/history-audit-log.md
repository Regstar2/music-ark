# history-audit-log

## Назначение

Журнал важных действий MusicArk.

## Отвечает за

- фиксировать сканы;
- фиксировать скачивания и ошибки;
- фиксировать импорт файлов;
- фиксировать torrent-задачи;
- фиксировать изменения метаданных;
- фиксировать решения конфликтов;
- фиксировать операции синхронизации;
- фиксировать загрузки и замены треков;

## Связи

- [[history-audit-log]] -> [[storage]]
- [[history-audit-log]] -> [[sync-executor]]
- [[history-audit-log]] -> [[download-system]]
- [[history-audit-log]] -> [[metadata-engine]]
- [[history-audit-log]] -> [[conflict-resolver]]
- [[history-audit-log]] -> [[ui]]

## Примечания

Любая операция, меняющая состояние коллекции, должна оставлять след. Программа без журнала — это человек без памяти, только быстрее ломает данные.

## Реализация v0.1

На `v0.1-core-foundation` добавлен минимальный storage-backed audit log:

- SQLite таблица `audit_log`;
- модель `AuditEvent`;
- репозиторий `AuditLogRepository.append(...)`.

Этого достаточно для первых операций ядра до появления полноценного [[sync-executor]] и [[metadata-engine]].

## Расширение v0.3

В `v0.3-yandex-scan` каждый запуск `YandexMusicProvider.scan_all(...)` добавляет событие:

- `event_type=provider_scan`
- `entity_type=provider`
- `entity_id=yandex_music`
- `status=success` или ошибка через исключение.

## Расширение v0.4

Локальный скан добавляет событие:

- `event_type=local_scan`
- `entity_type=provider`
- `entity_id=local_library`
- `details` содержит путь скана и счётчики `indexed/failed`.

## Расширение v0.5

Download-system добавляет события:

- `download_task_created`;
- `download_task_completed`;
- `download_task_failed`.

## Расширение v0.6

Yandex download tasks используют те же события `download_task_*`, что и local import,
поэтому ошибки и успешные загрузки треков Яндекс Музыки видны в общем журнале.

## Расширение v0.7

Matching-engine добавляет события:

- `matching_run`;
- `matching_conflict_accepted`.
