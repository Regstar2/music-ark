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
