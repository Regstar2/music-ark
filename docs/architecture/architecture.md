# MusicArk Architecture — v0.5

## Product boundaries

MusicArk has three top-level desktop flows sharing one SQLite database while keeping network, filesystem, and analytical responsibilities separate:

```text
Flutter desktop
        ↓
musicark.mvp_bridge
   ├──────────────────────┬──────────────────────┐
   ↓                      ↓                      ↓
YandexLibraryService  LocalLibraryService   MatchingService
   ↓                      ↓                      ↓
Yandex provider/cache Local scanner/index   Input identity adapter
                                                  ↓
                                          LocalMatchIndex
                                                  ↓
                                        CandidateGenerator
                                                  ↓
                                           MatchScorer
                                                  ↓
                                          MatchDecision
                                                  ↓
                                   MatchingStorageRepository
                                                  ↓
                                             SQLite
```

Matching never calls the Yandex network provider. It operates only on cached provider collections and the local index.

## Matching layers

### MatchingInputRepository

The active v0.3/v0.4 Yandex cache stores collection membership in `provider_collection_items`, while legacy canonical code already uses `provider_tracks`. The input adapter materializes a unique `(provider_id, external_id)` identity set into `provider_tracks` before matching. One track appearing in Liked and several playlists is processed once.

### LocalMatchIndex

`local_audio_files` remains owned by Local Library. Matching-specific compact columns (`normalized_title`, `normalized_artists_text`, `duration_bucket`) are refreshed once before a run and indexed by SQLite. This avoids coupling the v0.4 scanner to matching while also avoiding normalization of the whole local collection for every provider query.

### CandidateGenerator

Candidate generation performs a small series of indexed SQL lookups and returns at most 40 candidates per provider identity. It does not load the complete Local Library and contains no Cartesian-product loop.

### MatchScorer

Pure local scoring consumes structured provider/local metadata. Title similarity uses stdlib `difflib`; artists are normalized as an order-independent set; duration and album are secondary. Filename is fallback only. The strict `yandex_<track_id>.<ext>` filename convention is a strong exact-ID signal.

### MatchDecision

Policy is centralized in `matching/policy.py`:

```text
AUTO_MATCH_THRESHOLD = 0.90
CONFLICT_THRESHOLD   = 0.70
AMBIGUITY_MARGIN     = 0.04
```

The second-best candidate matters. A strong but ambiguous pair becomes `conflict` rather than an arbitrary match.

### MatchingStorageRepository

Persists automatic results in batches, reuses canonical `tracks` and confirmed `track_links`, and extends `match_conflicts` for multiple ranked candidates and rejection history. `matching_results` provides one current state per provider identity.

Manual match state outranks automatic state. A rejected candidate is excluded from later automatic candidate generation.

## SQLite v1.4.0

Forward migration from v0.4 `1.3.0` adds:

- matching index columns/indexes on `local_audio_files`;
- indexes for provider/local link queries;
- `matching_results` keyed by `(provider_id, external_id)`;
- score breakdown/rank/matcher-version/update fields on `match_conflicts`.

No Yandex cache, Local Library roots/files, canonical links, or credentials are dropped.

## Incremental matching

Each result records `matcher_version`, a provider metadata fingerprint, and a Local Library fingerprint. Unchanged automatic results can be skipped. Provider metadata changes or Local Library changes allow recalculation. Missing linked local files are invalidated before a run.

## Bridge boundary

Matching bridge commands are:

```text
matching_summary
matching_run
matching_results
matching_result
matching_accept
matching_reject
```

Listing supports `limit`, `offset`, `status`, `search`, and sort. The Flutter process boundary continues to use argument arrays with `Process.run(..., runInShell: false)`; no user value is interpolated into a shell command.

## Safety / privacy

The matching path is read-only toward audio files and Yandex Music. It performs no download, metadata mutation, file rename/move/delete, playlist edit, like/dislike, or upload. Local metadata is not sent to external matching or metadata services.

## Future boundary

v0.6 Missing Tracks can consume provider identities whose `matching_results` have no accepted local match. v0.5 does not implement download or the Missing Tracks product workflow.
