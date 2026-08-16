# sync-executor

## Назначение

Production execution boundary MusicArk v0.8 применяет только подтверждённые безопасные операции текущего Controlled Sync Plan.

## Apply contract

```text
explicit confirm
→ plan fingerprint / target validation
→ execution-time Coverage + triage recheck
→ active queue dedup recheck
→ DownloadService.enqueue(external_id)
→ persist task id / skip / failure
```

Baseline Apply **только ставит задачи в очередь**. Он не вызывает global `runQueue()`, не запускает unrelated queued tasks и не содержит собственной HTTP download implementation.

## Safety

v0.8 не выполняет:

- delete/move/rename local files;
- metadata edits;
- Yandex like/playlist/upload mutations;
- replacement downloads для Different Version;
- legacy `UPLOAD_CANDIDATE`, `REPLACE_CANDIDATE`, `UPDATE_METADATA_CANDIDATE` и другие старые dangerous operations.

Legacy plans остаются читаемыми для audit, но production v0.8 executor отказывает в их Apply.

Каждый actionable operation проходит execution-time revalidation. Если трек уже Covered, больше не Wanted или уже queued/running, новая task не создаётся. Повторный Apply не создаёт duplicate active task.

## Реализация

- `src/musicark/sync/service.py` — production orchestration;
- `src/musicark/sync/safe_execution.py` — compatibility facade, делегирующий тому же safe boundary;
- `src/musicark/sync/executor.py` — exports production Controlled Sync boundary; experimental upload helper остаётся отдельным legacy/experimental кодом и не вызывается из v0.8 Sync.

## Связи

- [[sync-executor]] → [[sync-planner]];
- [[sync-executor]] → production `DownloadService.enqueue()`;
- [[sync-executor]] → [[storage]];
- [[sync-executor]] → [[history-audit-log]];
- [[sync-executor]] → [[ui]].
