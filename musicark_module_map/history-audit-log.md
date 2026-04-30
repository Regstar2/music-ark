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
