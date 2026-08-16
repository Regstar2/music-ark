# MusicArk Architecture — v0.8.0

## Active application boundaries

```text
Flutter desktop
   ├── Yandex UI        → YandexLibraryService/cache
   ├── Local Library    → LocalLibraryService/index
   ├── Matching         → MatchingService
   ├── Missing          → CoverageRepository
   ├── Downloads        → DownloadService
   └── Sync             → SyncService
                              ├── SyncPlanner (read only)
                              ├── SyncStorageRepository
                              ├── CoverageRepository
                              ├── Matching/Local fingerprints
                              └── DownloadService (enqueue only on Apply)
```

v0.8 does not introduce a second implementation of Coverage, Matching, Variant detection, Local indexing, or provider downloading.

## Desired and actual state

The desired state is the unique provider identity set from **active cached Yandex collection membership**. Supported scope is all active collections, Liked, or one Yandex Playlist. Duplicate occurrences and memberships are canonicalized through the existing Coverage SQL using `(provider_id, external_id)`.

Actual state is the existing v0.6 Coverage view:

```text
covered / missing / needs_review / not_analyzed
```

Variant remains a separate dimension. `UNCERTAIN`, `ALTERED`, and `DIFFERENT_VERSION` create review items but never turn an accepted identity into Missing.

## Controlled Sync Planner

`SyncPlanner` is local-only and side-effect free with respect to product state. It reads Coverage in SQL-backed batches, reads the Local Library fingerprint once, reads active production download tasks in one query, computes informational local-only rows in SQL, creates an immutable plan snapshot, and persists it.

It does not run Matching, Variant analysis, HTTP downloads, filesystem writes, metadata edits, or Yandex mutations.

Production operations are:

```text
ENQUEUE_DOWNLOAD
REVIEW_IDENTITY
REVIEW_VARIANT
USER_DECISION_REQUIRED
LOCAL_ONLY
```

Legacy enum values remain only for historical row compatibility.

## Fingerprint and staleness

A plan fingerprint contains planner version, scope, selected download target, selected-scope active membership, authoritative Coverage/Matching result state, user triage, Variant status, and current Local Library fingerprint. Playback/current queue position is excluded.

Relevant state change after plan creation marks the plan `stale`; Apply is refused. Rebuild always creates a new plan id.

## Apply boundary

`SyncService.apply()` requires explicit confirmation, validates the plan, checks the exact target snapshot, then rechecks every pending `ENQUEUE_DOWNLOAD` operation against current Coverage and triage. It checks the active production queue and finally calls:

```python
DownloadService.enqueue(external_id, provider_id="yandex_music")
```

It never instantiates the legacy `DownloadSystem` and never calls the global `runQueue()`. Baseline Apply only enqueues task ids belonging to this plan; actual transfer remains on the Downloads workflow.

This double validation protects races such as a planned track becoming Covered between plan creation and execution.

## Legacy Sync

Historical `sync_plans` / `sync_operations` remain readable after migration. Legacy operations such as upload/replace/metadata candidates are unsupported by the v0.8 executor and cannot execute through `SyncSafeExecutor`; that compatibility entry point delegates to `SyncService`.

## Storage — schema 1.8.0

`1.7.0 → 1.8.0` extends the existing sync tables in place. Plan snapshot fields include planner version, scope, target, fingerprint, applied timestamp/result. Operations gain execution status/result timestamps. Existing Yandex cache, Local Library, matching links/conflicts, Variant results, Coverage actions, Downloads/settings, and sync history are preserved.

No credentials, authorization headers, provider direct URLs, or audio blobs belong in sync tables.

## Safety invariant

Normal Sync Apply performs zero local-file delete/rename/move/tag mutations and zero Yandex mutations. Local-only means informational, and playlist scope uses **Outside this scope**, not “extra/delete”.
