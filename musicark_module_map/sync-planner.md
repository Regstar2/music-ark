# sync-planner

## Назначение

Модуль построения плана действий перед изменениями коллекции.

## Отвечает за

- сравнивать состояние сервиса и локального архива;
- использовать предыдущие снимки из [[storage]];
- получать связи из [[matching-engine]];
- создавать SyncOperation;
- создавать [[download-task]] для будущих загрузок;
- отправлять конфликты в [[conflict-resolver]];
- передавать подтверждённый план в [[sync-executor]];

## Связи

- [[sync-planner]] -> [[sync-executor]]
- [[sync-planner]] -> [[download-system]]
- [[sync-planner]] -> [[download-task]]
- [[sync-planner]] -> [[matching-engine]]
- [[sync-planner]] -> [[conflict-resolver]]
- [[sync-planner]] -> [[ui]]
- [[sync-planner]] -> [[history-audit-log]]
- [[sync-planner]] -> [[storage]]

## Правила

[[sync-planner]] не выполняет опасные действия. Он только строит план. Удаление, замена и массовая загрузка — только после подтверждения.
