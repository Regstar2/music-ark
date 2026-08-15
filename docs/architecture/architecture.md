# MusicArk Architecture — v0.6.0

## Product boundaries

MusicArk keeps provider access, local indexing, identity matching, variant verification, and library coverage as separate responsibilities over one SQLite database:

```text
Flutter desktop
        ↓
musicark.mvp_bridge
   ├──────────────────────┬──────────────────────┬─────────────────────────┐
   ↓                      ↓                      ↓                         ↓
YandexLibraryService  LocalLibraryService   MatchingService      VariantDetectionService
   ↓                      ↓                      ↓                         ↓
Yandex provider/cache Local scanner/index   identity matching         matched pair only
                                                  ↓                         ↓
                                         MATCHED/CONFLICT/UNMATCHED   variant evidence
                                                  └──────────┬──────────────┘
                                                             ↓
                                                  LibraryCoverageService
                                                             ↓
                                                    CoverageRepository
                                                             ↓
                                                           SQLite
```

Matching, variant verification, and coverage never need the Yandex network provider for analytical queries. They work from cached provider metadata, Local Library state, and persisted authoritative results.

## Identity Matching — v0.5

### MatchingInputRepository

Materializes a unique `(provider_id, external_id)` identity set from cached collection membership into `provider_tracks`. A track present in Liked and multiple playlists is processed once. v0.6 additionally canonicalizes playlist duplicate occurrence storage keys from `payload_json.external_id`, so synthetic collection keys never become fake provider identities.

### LocalMatchIndex / CandidateGenerator / MatchScorer

`local_audio_files` stays owned by Local Library. Compact normalized title/artist/duration indexes support bounded candidate lookups. Detailed scoring receives at most a small candidate set instead of a Cartesian `Yandex × Local` product.

The strict `yandex_<track_id>.<ext>` filename convention remains a strong exact-ID identity signal. Semantic words such as Live/Remix/Acoustic are not erased by normalization.

### MatchDecision

Identity policy remains unchanged:

```text
AUTO_MATCH_THRESHOLD = 0.90
CONFLICT_THRESHOLD   = 0.70
AMBIGUITY_MARGIN     = 0.04
```

A strong but ambiguous identity becomes `CONFLICT`, not an arbitrary automatic match. Manual accepted/rejected decisions outrank later automatic matching.

## Variant Detection — v0.5.1

Variant detection is an additional layer. It never changes `MATCHED / CONFLICT / UNMATCHED` or replaces identity confidence with one combined score.

### MetadataVariantDetector

Extracts semantic variant markers from provider/local title, album, and weak filename evidence. It also carries provider `explicit` (mapped from Yandex `content_warning`) and any locally known explicit flag. Explicit mismatch is evidence only; it is not a censorship verdict.

### ReferenceAudioResolver / ReferenceAudioAcquirer

Deep verification requires an exact reference for the provider identity. Only these strict filename conventions are accepted:

```text
yandex_<track_id>.<ext>
yandex-<track_id>.<ext>
```

The resolver first checks `.musicark/downloads/yandex`, then indexed local files. Arbitrary numbers elsewhere in a path are ignored. The current tested service may, during an **explicit single-track `variant_run`**, use the bounded `ReferenceAudioAcquirer` to obtain one exact reference if none is available. `variant_run_all_available` remains bounded to already-resolvable references and does not silently download a library.

Reference acquisition is a verification mechanism only: an acquired reference is not indexed into Local Library and does not create `track_links`.

### AudioDecoder / FfmpegAudioDecoder

`AudioDecoder` is an abstraction. `FfmpegAudioDecoder` is the v0.5.1 adapter and normalizes supported inputs through a pipe to:

```text
mono
signed 16-bit PCM
11025 Hz
```

No giant temporary WAV is required. The decoded buffer stays compact and is never stored in SQLite. ffmpeg is optional: if it is absent, the app, identity matching, and v0.6 Coverage continue working and variant output remains conservative.

### AudioAligner

A bounded coarse alignment compares normalized energy envelopes within ±15 seconds. This covers encoder delay, short leading silence, and modest start offsets without unrestricted dynamic alignment.

### SegmentComparator

After alignment, the recording is compared in policy-controlled overlapping windows (`2.0 s`, `0.75 s` hop). Similarity combines normalized energy-envelope shape, compact phase-insensitive spectral evidence, zero-crossing rate, and derivative evidence.

Low-similarity neighboring windows are merged into `AlteredRegion` values containing start/end/mean/minimum similarity. Isolated mild outliers are ignored.

### VariantClassifier

Classification uses several explainable signals instead of one magic threshold:

- semantic marker mismatch;
- explicit evidence;
- duration delta;
- global audio similarity;
- median window similarity;
- low-similarity-window ratio;
- longest altered region;
- altered region count.

The precision rule is conservative: a false `SAME` is worse than `UNCERTAIN`.

A possible clean/censored interpretation is emitted only when several signals agree. The reason is named `possible_clean_or_censored_variant`; it is not presented as certain lyric classification.

## Library Coverage — v0.6

Coverage is an application-level derived view. It consumes current v0.5 identity state instead of running its own candidate generation/scoring.

```text
active provider collection membership
        +
matching_results / track_links
        +
local_audio_files
        +
track_variant_results
        +
provider_track_actions
        ↓
LibraryCoverageService
        ↓
CoverageRepository (SQL)
        ↓
covered / missing / needs_review / not_analyzed
```

Primary truth rules:

- `covered`: current accepted automatic/manual identity, available indexed local file, and accepted `track_links` relationship;
- `missing`: current authoritative `UNMATCHED` with no accepted current local link;
- `needs_review`: `CONFLICT`, stale manual accepted decision, or invalid accepted link;
- `not_analyzed`: no matching result or stale automatic result after matcher/provider/Local Library fingerprint change.

`not matched == missing` is forbidden. Variant state is joined as a separate secondary dimension for covered identities; `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, and `NOT_CHECKED` never increase Missing.

The reference cache is also separate. `reference exists → covered` is forbidden because coverage requires a normal indexed Local Library link.

### Active dataset / scopes

Coverage starts from active `provider_collection_items` / `provider_collection_snapshots`, canonicalizes provider identity from payload `external_id`, and deduplicates globally by `(provider_id, external_id)`. All collection memberships are aggregated for the row/detail UI. Liked and a specific playlist can be used as scopes; playlist scope preserves provider order.

Tracks removed from all active Yandex collections cannot appear as zombie Missing rows. Historical `wanted/ignored` rows may remain stored but do not enter an active query unless that provider identity is active again.

### SQL / performance boundary

Summary, list, search, filters, sorting, and pagination are SQL-backed CTE/join queries. Flutter does not receive the entire 5k–20k derived provider library to compute technical coverage, and list queries do not issue one database query per provider track.

## SQLite v1.6.0

Migration history is forward-only:

```text
1.3.0 Local Library
  ↓
1.4.0 Identity Matching
  ↓
1.5.0 Variant Detection
  ↓
1.6.0 Coverage user actions
```

v1.5 adds `track_variant_results` with primary key `(provider_id, external_id, local_file_id)` and stores variant evidence/fingerprints without PCM/audio blobs.

v1.6 adds only:

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

No row means `unreviewed`. Coverage status itself is not persisted. Yandex cache, Local Library roots/files, `matching_results`, `track_links`, `match_conflicts`, manual decisions, and `track_variant_results` are preserved.

## Incremental analysis / invalidation

Identity matching retains its v0.5 matcher/provider/library fingerprints. Automatic results whose matcher/provider/local-library fingerprint is no longer current are `not_analyzed` for Coverage until Matching reruns. Manual links reuse v0.5 manual stale/fingerprint semantics and become `needs_review` when stale.

Variant results retain their independent provider/local/reference/analyzer fingerprints and are recomputed by the existing v0.5.1 verification workflow when required. Coverage does not invent a second variant cache-validity model.

## Bridge boundary

Identity commands remain:

```text
matching_summary
matching_run
matching_results
matching_result
matching_accept
matching_reject
```

Variant commands remain separate:

```text
variant_capabilities
variant_summary
variant_run
variant_run_all_available
variant_result
variant_results
```

Coverage adds:

```text
coverage_summary
coverage_tracks
coverage_track
coverage_collections
coverage_set_action
coverage_set_actions
```

Bulk provider IDs use structured JSON transport through the existing process boundary, not unsafe shell concatenation. Flutter launches Python with `runInShell: false`.

## Safety / privacy

All analytical layers are read-only toward user music and Yandex Music. v0.6 performs no missing-track download/source selection, metadata mutation, rename/move/delete, playlist edit, like/dislike, or upload. Local metadata/paths/matching/missing-list data are not sent to third-party services. Existing bounded v0.5.1 explicit reference acquisition remains verification-only and cannot establish Local Library coverage.

## Future boundary

v0.7 can consume the simple derived condition:

```text
coverage_status = missing
AND user_action = wanted
```

v0.6 deliberately does not implement actual download execution or source selection.
