# MusicArk Architecture — v0.5.1

## Product boundaries

MusicArk keeps provider access, local indexing, identity matching, and variant verification as separate responsibilities over one SQLite database:

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
                                         MATCHED/CONFLICT/UNMATCHED   metadata evidence
                                                                            ↓
                                                                    strict reference resolver
                                                                            ↓
                                                                      ffmpeg decoder
                                                                            ↓
                                                                         aligner
                                                                            ↓
                                                                    segment comparator
                                                                            ↓
                                                                     variant classifier
                                                                            ↓
                                                       SAME/ALTERED/DIFFERENT_VERSION/
                                                           UNCERTAIN/NOT_CHECKED
                                                                            ↓
                                                                          SQLite
```

Matching and variant verification never call the Yandex network provider. They work from cached provider metadata and local files already known to MusicArk.

## Identity Matching — v0.5

### MatchingInputRepository

Materializes a unique `(provider_id, external_id)` identity set from cached collection membership into `provider_tracks`. A track present in Liked and multiple playlists is processed once.

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

### ReferenceAudioResolver

Deep verification requires an exact local reference for the provider identity. Only these strict filename conventions are accepted:

```text
yandex_<track_id>.<ext>
yandex-<track_id>.<ext>
```

The resolver first checks `.musicark/downloads/yandex`, then indexed local files. Arbitrary numbers elsewhere in a path are ignored.

### AudioDecoder / FfmpegAudioDecoder

`AudioDecoder` is an abstraction. `FfmpegAudioDecoder` is the v0.5.1 adapter and normalizes supported inputs through a pipe to:

```text
mono
signed 16-bit PCM
11025 Hz
```

No giant temporary WAV is required. The decoded buffer stays compact and is never stored in SQLite. ffmpeg is optional: if it is absent, the app and metadata matching continue working and the result remains conservative.

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

A possible clean/censored interpretation is emitted only when several signals agree (provider explicit metadata, close duration, high overall recording similarity, and localized divergence). The reason is named `possible_clean_or_censored_variant`; it is not presented as certain lyric classification.

## SQLite v1.5.0

Migration history is forward-only:

```text
1.3.0 Local Library
  ↓
1.4.0 Identity Matching
  ↓
1.5.0 Variant Detection
```

v1.5 adds `track_variant_results` with primary key `(provider_id, external_id, local_file_id)`. It stores variant status, metadata evidence, audio similarity, reasons, altered regions, provider/local/reference fingerprints, analyzer version, reference path, and timestamps.

No PCM/audio blobs are stored. Yandex cache, Local Library roots/files, `matching_results`, `track_links`, `match_conflicts`, and manual decisions are preserved.

## Incremental analysis / invalidation

Identity matching retains its v0.5 matcher/provider/library fingerprints.

Variant results have independent fingerprints for:

- provider metadata relevant to variant semantics;
- local path + file size + mtime;
- reference path + file size + mtime;
- `ANALYZER_VERSION`.

Unchanged successful results skip re-decode. Local/reference/provider changes invalidate the cache. Technical failures are not treated as permanently cacheable, so installing ffmpeg or repairing a file can recover without deleting the DB.

## Performance boundary

Audio verification occurs only after a `MATCHED` identity (including manual accepted links). `UNMATCHED` and unresolved `CONFLICT` rows are not decoded. `variant_run_all_available` further restricts work to pairs with resolvable exact-ID references and isolates per-file failures.

All audio operations stay Python-side. PCM never crosses Flutter ↔ Python. Flutter starts bridge processes asynchronously, keeping heavy decoding outside the UI isolate.

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

Variant commands are separate:

```text
variant_capabilities
variant_summary
variant_run
variant_run_all_available
variant_result
variant_results
```

No variant logic is added to `matching_run`.

## Safety / privacy

Both analytical layers are read-only toward music files and Yandex Music. They perform no automatic download, metadata mutation, rename/move/delete, playlist edit, like/dislike, or upload. Local metadata/audio is not sent to external matching, metadata, fingerprint, or ML services.

## Future boundary

v0.6 Missing Tracks can consume identity results with no accepted local match. v0.5.1 only improves verification of already established links; it does not implement download or sync.
