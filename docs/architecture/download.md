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

## Eligibility and one-click UX

The backend invariant for a normal enqueue remains:

```text
coverage_status = missing
user_action = wanted
```

This is not a multi-step requirement for the user. On a Missing row, **Скачать** is a one-click action: Flutter first persists `wanted`, immediately enqueues the exact provider identity, and starts/joins the user download queue. The explicit `Нужен` control remains useful for triage and bulk intent, but it is not required before downloading one track.

The service rechecks eligibility immediately before execution. If the state genuinely changed before transfer, the task becomes `skipped` and no duplicate is downloaded.

One active user task is allowed per download-provider identity `(yandex_music_download, external_id)`. Multiple Liked/playlist memberships therefore remain one queue item.

## Queue persistence and legacy isolation

The existing `download_tasks` table is extended in place by schema 1.7.0. New state includes downloaded/total bytes, cancellation flag, target root, error code, and update timestamp. Download settings persist both Local Library ownership and the exact folder selected by the user.

Lifecycle:

```text
queued → running → completed
               ↘ failed → retry → queued
               ↘ cancelled
queued → cancelled
queued → skipped
```

A process restart converts persisted v0.7 user `running` tasks to retryable `failed` with `error_code=interrupted`. No fake pause/resume state is presented.

The baseline worker is sequential (`max concurrency = 1`). This is a deliberate bounded-concurrency implementation; the queue can contain hundreds of entries without opening hundreds of transfers.

The SQLite table also contains historical/reference-acquisition tasks. `musicark.download.bridge` explicitly scopes the Downloads page, worker, recovery, retry/cancel and clear-history actions to v0.7 `provider_download` user tasks. Internal Variant reference-cache history is neither displayed nor executed/deleted by the user Downloads surface.

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

The folder picker selects the **actual user download directory**. MusicArk persists that exact normalized path in `download_settings`; switching pages or recreating `DownloadService` must not replace it with a parent Local Library root or another derived path.

The selected folder must either be a Local Library root or lie under an existing root. If it is outside all configured roots, it becomes a Local Library root. Each task snapshots both `target_root_id` and exact `target_folder` at enqueue time so later settings changes do not move an already queued task.

Databases created before exact `target_path` persistence remain forward-compatible: an old root-only setting falls back to the historical `<root>/MusicArk` target until the user selects a folder again.

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

v0.5.1 reference files in `.musicark/downloads/yandex/` remain verification cache only. They are not v0.7 destinations, are not indexed into Local Library, cannot make Coverage `covered`, and are hidden from the v0.7 user Downloads history.

## File actions / playback boundary

Raw local paths are not permanently printed on track/download cards. They are shown only after an explicit **Показать путь** action.

For completed/local tracks the desktop UI exposes:

- **Воспроизвести** — open the local audio file with the operating system's associated/default player;
- **Открыть расположение файла** — reveal/select the actual file in Explorer/Finder (or open its directory on Linux).

This is intentionally a v0.7 file-launch baseline, not an embedded media engine. A native MusicArk player with play/pause/seek/queue is a separate future feature.

## Bridge/UI boundary

Flutter receives only JSON task metadata and periodically polls while a worker is active. Binary chunks never cross the Flutter↔Python boundary. The dedicated bridge exposes summary/list/enqueue/bulk-enqueue/run/retry/cancel/history/settings/target/recovery operations using `Process.run(..., runInShell: false)` from Flutter.

The Downloads page polls at 800 ms while queue execution is active and otherwise refreshes on demand. The queue/history page remains available for progress, cancellation, retry and diagnostics, but ordinary single-track download does not require visiting it.
