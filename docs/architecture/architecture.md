# MusicArk Architecture — v0.6.0

## Product layers

```text
Flutter desktop
   ↓ process bridge
YandexLibraryService ─ LocalLibraryService ─ MatchingService ─ VariantDetectionService
                                                  │                  │
                                                  └──────┬───────────┘
                                                         ↓
                                             LibraryCoverageService
                                                         ↓
                                                CoverageRepository
                                                         ↓
                                                       SQLite
```

Identity matching and variant verification remain separate. Coverage is a third, read-only analytical composition over their authoritative results.

## Identity coverage

Coverage derives `covered`, `missing`, `needs_review`, and `not_analyzed` at query time. Automatic results are current only when v0.5 matcher version, provider fingerprint, and Local Library fingerprint remain current. Manual accepted links reuse v0.5 manual-stale semantics and local/provider fingerprints. No independent stale algorithm is persisted.

`covered` additionally requires an available indexed `local_audio_files` row and the accepted `track_links` relationship. Therefore an exact reference file in `.musicark/downloads/yandex` cannot accidentally count as local coverage.

## Variant boundary

Variant state is joined only as a secondary dimension for covered identities. It never changes primary coverage. The v0.5.1 explicit `variant_run` path may acquire one exact provider reference when needed; this bounded verification cache is not Local Library and not v0.7 download.

## Active provider dataset

Coverage starts from active `provider_collection_items` / `provider_collection_snapshots`, canonicalizes provider identity from payload `external_id`, and deduplicates globally by `(provider_id, external_id)`. Collection membership remains available to the UI. A playlist scope orders by the minimum provider position for that identity.

## SQL/performance boundary

Summary, list, search, filters, sorting and pagination are SQL-backed CTE/join queries. Flutter never receives the full 5k–20k derived library only to compute status. No per-track database query loop is used for list pages.

## Persistence / schema 1.6.0

Coverage status is not persisted. v1.6 adds only:

```text
provider_track_actions(
  provider_id,
  external_id,
  action CHECK wanted|ignored,
  created_at,
  updated_at,
  PRIMARY KEY(provider_id, external_id)
)
```

No row = `unreviewed`. The migration is forward-only and preserves all previous tables/data.

## Bridge boundary

Coverage uses separate commands: `coverage_summary`, `coverage_tracks`, `coverage_track`, `coverage_collections`, `coverage_set_action`, and `coverage_set_actions`. Bulk IDs are transported as structured JSON in an environment payload; they are not interpolated into a shell string. Flutter launches Python with `runInShell: false`.

## Safety

v0.6 does not download missing tracks, alter local files, mutate Yandex, or send local paths/matching/missing data to third-party services. Existing v0.5.1 bounded explicit reference acquisition remains unchanged and cannot establish Local Library coverage.
