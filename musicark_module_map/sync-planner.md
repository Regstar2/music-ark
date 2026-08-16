# sync-planner

## Назначение

Production planner MusicArk v0.8 строит **immutable dry-run Sync Plan** для направления `Yandex desired → Local actual`.

## Authoritative inputs

Planner не определяет наличие локальной копии по имени файла и не повторяет Matching/Coverage. Он читает:

- active Yandex collection membership;
- `CoverageRepository` (`covered / missing / needs_review / not_analyzed`);
- `matching_results` и accepted `track_links` через Coverage state;
- `provider_track_actions` (`wanted / ignored / unreviewed`);
- `track_variant_results`;
- Local Library fingerprint/state;
- active production `download_tasks` только для queue deduplication;
- текущий production download target.

Scope: вся активная Yandex Library, `Мне нравится` или один active Yandex Playlist. Identity — `provider_id + external_id`; duplicate membership не создаёт duplicate operation.

## Production operations v0.8

- `ENQUEUE_DOWNLOAD` — только `missing + wanted`;
- `USER_DECISION_REQUIRED` — `missing + unreviewed`;
- `REVIEW_IDENTITY` — identity conflict / matching required;
- `REVIEW_VARIANT` — covered track с uncertain/altered/different-version result;
- `LOCAL_ONLY` — только informational; для playlist это `Outside this scope`.

Covered и ignored Missing отражаются в summary без тысяч NOOP rows.

## Safety

Создание плана не запускает Matching, Variant verification, HTTP download, filesystem mutations или Yandex mutations. Legacy enum values сохраняются для чтения старых rows, но новый planner их не генерирует.

Plan fingerprint включает planner version, scope, active membership, Coverage/Matching/Local state, triage, Variant state и exact download target. Playback state исключён. Download queue не является snapshot truth: duplicate queue state повторно проверяется непосредственно перед enqueue.

## Связи

- [[sync-planner]] → Coverage/Matching/Local authoritative state;
- [[sync-planner]] → [[storage]] (`sync_plans`, `sync_operations`);
- [[sync-planner]] → [[sync-executor]] только после preview/confirmation;
- [[sync-planner]] → [[history-audit-log]].
