# Download Architecture — v0.7.0

## Boundary

v0.7 evolves the existing download subsystem instead of introducing a second queue or Yandex downloader.

```text
Flutter
  ↓
musicark.download.bridge
  ↓
DownloadService
  ├── CoverageRepository
  ├── DownloadStorageRepository
  ├── DownloadProviderRegistry
  │     └── YandexMusicDownloadProvider
  ├── LocalLibraryService
  │     └── LocalFileIndexer
  ├── MatchingStorageRepository
  └── SystemCredentialStore
```

The legacy `DownloadProviderRegistry` and `YandexMusicDownloadProvider` remain reusable. The legacy `DownloadSystem` is compatibility code only; production v0.7 orchestration lives in `DownloadService` because the old system stopped at a legacy local-file row and could leave `library_root_id = NULL`.

## Eligibility

A normal enqueue requires the current derived state:

```text
coverage_status = missing
user_action = wanted
```

The service rechecks the same condition immediately before execution. If the state changed, the task becomes `skipped` and no duplicate is downloaded.

One active task is allowed per download-provider identity `(yandex_music_download, external_id)`. Multiple Liked/playlist memberships therefore remain one queue item.

## Queue persistence

The existing `download_tasks` table is extended in place by schema 1.7.0. New state includes downloaded/total bytes, cancellation flag, target root, error code, and update timestamp. The selected default target root is stored in `download_settings`.

Lifecycle:

```text
queued → running → completed
               ↘ failed → retry → queued
               ↘ cancelled
queued → cancelled
queued → skipped
```

A process restart converts persisted `running` to retryable `failed` with `error_code=interrupted`. No fake pause/resume state is presented.

The baseline worker is sequential (`max concurrency = 1`). This is a deliberate bounded-concurrency implementation; the queue can contain hundreds of entries without opening hundreds of transfers.

## Credentials and provider URLs

`DownloadService` obtains the Yandex token from `SystemCredentialStore` and passes it directly into `YandexMusicDownloadProvider`. The provider may retain legacy token fallback only for older tooling/reference workflows.

Forbidden persistent values include token, authorization/cookie data, and temporary direct download URLs. `DownloadStorageRepository` rejects sensitive task-payload keys. Direct links exist only in provider execution memory.

## Transfer

The provider resolves the exact requested Yandex track ID and chooses the highest available bitrate for `quality=best`. HTTP content is streamed directly to disk:

```text
<final>.part
   ↓ atomic promotion
<final>
```

When `Content-Length` exists, the provider reports real `(downloaded_bytes, total_bytes)`. Unknown total remains indeterminate. `DownloadService` throttles SQLite progress writes by time/byte thresholds.

Running cancellation is cooperative: the provider checks a callback between chunks. The callback reads the persisted cancellation flag at a bounded cadence. Cancellation/failure removes `.part`; v0.7 does not implement Range resume.

## Destination and path safety

The selected folder is a Local Library root or lies under an existing root. New downloads use the managed child:

```text
<root>/MusicArk/
```

Each task snapshots `target_root_id` and `target_folder` at enqueue time.

Filenames are sanitized for Windows reserved characters/names, trailing spaces/dots, and are kept as leaf names. The stable source ID is included:

```text
Artist - Title [yandex_123456].mp3
```

The provider resolves the final path and verifies its parent is the task target directory, preventing metadata-driven traversal.

## Post-download Local Library pipeline

HTTP success is not a terminal success condition.

```text
provider transfer
  ↓
non-empty atomic file
  ↓
LocalMetadataReader
  ↓
LocalFileIndexer.index_file(path, root)
  ↓
LocalLibraryStorageRepository.apply_scan(... allow_removals=False)
  ↓
local_audio_files with library_root_id + normalized_path + metadata
  ↓
MatchDecision(method=exact_id, confidence=1.0)
  ↓
MatchingStorageRepository.persist_batch
  ↓
CoverageRepository re-read
  ↓
covered
```

`LocalFileIndexer` indexes only the completed file and never performs a full root walk. It reuses the v0.4 metadata/storage path and disables removal reconciliation for this single-file operation.

The exact matching decision computes the global Local Library fingerprint *after* indexing, keeping v0.5 automatic-freshness semantics valid. No fuzzy candidate decision is needed because acquisition started from an exact provider identity.

Variant analysis is not invoked and no `SAME` result is manufactured.

## Reference cache separation

v0.5.1 reference files in `.musicark/downloads/yandex/` remain verification cache only. They are not v0.7 destinations, are not indexed into Local Library, and cannot make Coverage `covered`.

## Bridge/UI boundary

Flutter receives only JSON task metadata and periodically polls while a worker is active. Binary chunks never cross the Flutter↔Python boundary. The dedicated bridge exposes summary/list/enqueue/bulk-enqueue/run/retry/cancel/history/settings/target/recovery operations using `Process.run(..., runInShell: false)` from Flutter.

The Downloads page polls at 800 ms while queue execution is active and otherwise refreshes on demand.
