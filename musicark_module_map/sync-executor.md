# sync-executor

## Назначение

Исполнитель подтверждённого плана синхронизации.

## Отвечает за

- выполнять операции по порядку;
- вызывать [[download-system]], [[providers]] и [[metadata-engine]];
- обрабатывать ошибки;
- делать операции возобновляемыми;
- обновлять [[storage]];
- писать в [[history-audit-log]];

## Связи

- [[sync-executor]] -> [[sync-planner]]
- [[sync-executor]] -> [[download-system]]
- [[sync-executor]] -> [[providers]]
- [[sync-executor]] -> [[metadata-engine]]
- [[sync-executor]] -> [[storage]]
- [[sync-executor]] -> [[history-audit-log]]
- [[sync-executor]] -> [[ui]]

## Примечания

Частичный провал должен быть нормальной ситуацией: что сделано, что упало, что можно повторить. Не надо превращать ошибку в туманную драму.

## Реализация v0.11

Модуль `src/musicark/sync/executor.py` содержит `execute_experimental_yandex_upload` — обёртка над экспериментальным пробником `musicark.providers.yandex_experimental_upload`.

## Реализация v1.0 (desktop MVP — безопасный путь)

`src/musicark/sync/safe_execution.py` экспортирует `SyncSafeExecutor` и `resolve_latest_plan_id`.

- Исполняются только неопасные операции типа `create_download_task` с парой (`yandex_download`, `yandex_music_download`).
- Остальные операции плана пропускаются с указанием причины; опасные — никогда не выполняются.
- Итог и отдельные шаги пишутся в [[history-audit-log]].

### Ре‑экспорт

`executor.py` реэкспортирует `SyncSafeExecutor` и `resolve_latest_plan_id` для удобства импорта (`from musicark.sync.executor import SyncSafeExecutor`).

Полноценное исполнение прочих типов операций плана (аплоад, массовые правки метаданных и т.д.) — только в следующих версиях.
