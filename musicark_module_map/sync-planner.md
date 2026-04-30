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

## Реализация v0.8

В `v0.8-sync-planner` реализован `SyncPlanner` в `src/musicark/sync/planner.py`:

- строит `SyncPlan` и `SyncOperation` в режиме dry-run;
- анализирует remote/local состояние и формирует операции:
  - `download_track`
  - `create_download_task`
  - `link_local`
  - `needs_review`
  - `mark_unavailable`
  - `update_metadata_candidate`
- сохраняет план в [[storage]];
- не выполняет опасные действия автоматически.
