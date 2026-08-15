# Release Checklist — v0.7.0 Download

## Automated validation

- [ ] `python -m unittest discover -s tests -p "test_*.py" -v` is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] schema initializes twice without error and reports `1.7.0`.
- [ ] realistic `1.6.0 → 1.7.0` migration preserves Yandex cache, Local Library, v0.5 matching/manual/conflict state, v0.5.1 Variant results, v0.6 actions, and legacy download tasks.
- [ ] v0.4 Local Library regression suite stays green.
- [ ] v0.5 Matching regression suite stays green.
- [ ] v0.5.1 Variant regression suite stays green.
- [ ] v0.6 Coverage regression suite stays green.
- [ ] v0.7 eligibility/dedup/progress/cancellation/recovery/integration tests are green.
- [ ] Flutter Downloads navigation/empty/queued/running/progress/indeterminate/retry/cancel/target tests are green.

## Eligibility / dedup

- [ ] only `missing + wanted` is an ordinary enqueue candidate.
- [ ] `missing + ignored` is not bulk-enqueued.
- [ ] `missing + unreviewed` is not bulk-enqueued.
- [ ] `covered + wanted` is not downloaded.
- [ ] `conflict/needs_review + wanted` is not downloaded.
- [ ] `not_analyzed + wanted` is not downloaded.
- [ ] `MATCHED + DIFFERENT_VERSION` is not automatically downloaded.
- [ ] enqueue state is rechecked immediately before transfer; stale/ineligible task becomes `skipped`.
- [ ] one Yandex identity in Liked + several playlists yields one task.
- [ ] repeated enqueue of one active identity yields one task.

## Provider / credentials

- [ ] production Download gets the Yandex token from `SystemCredentialStore`.
- [ ] token is not present in argv, `download_tasks`, `raw_payload_json`, SQLite, filenames, UI, audit, or logs.
- [ ] temporary direct download URL is not persisted/logged/displayed.
- [ ] best-quality selection is covered by tests.
- [ ] missing track / no download info / auth / network / HTTP failures have distinguishable error categories.
- [ ] Yandex failure never triggers YouTube/VK/torrent/web-search fallback.
- [ ] reference cache and user Download Library remain separate.

## Queue lifecycle

- [ ] user-visible states are queued/running/completed/failed/cancelled/skipped as applicable.
- [ ] fake Pause/Resume UI does not exist.
- [ ] queue survives restart.
- [ ] persisted `running` is recovered predictably to retryable `failed/interrupted`.
- [ ] completed tasks are not rerun by ordinary Run queue.
- [ ] Retry uses the same provider identity and does not create duplicate files.
- [ ] clearing completed history never deletes downloaded audio.
- [ ] worker concurrency is bounded; baseline v0.7 is sequential.

## Streaming / progress / cancellation

- [ ] audio is streamed to disk; no audio blobs are stored in SQLite.
- [ ] known `Content-Length` produces real downloaded bytes / total bytes / percentage.
- [ ] unknown length renders indeterminate progress rather than fake percentages.
- [ ] SQLite progress writes are throttled.
- [ ] transfer writes `<final>.part` and promotes atomically only after network completion.
- [ ] failure/cancel removes `.part` when resume is not implemented.
- [ ] running cancellation is cooperative between chunks; no arbitrary PID kill is used.
- [ ] v0.7 UI does not claim Range resume.

## Destination / file safety

- [ ] user selects a Local Library root/folder through the existing Windows folder picker.
- [ ] no configured root → no silent user download into `.musicark`.
- [ ] selected default root persists.
- [ ] queued task snapshots `target_root_id` / target folder.
- [ ] managed destination remains inside the selected Local Library root.
- [ ] Windows-invalid characters/reserved names/trailing dots/spaces are sanitized.
- [ ] stable Yandex external ID is present in filenames.
- [ ] provider metadata cannot cause path traversal.
- [ ] arbitrary existing local music is never overwritten/renamed/moved/deleted/tag-edited.
- [ ] real downloaded audio extensions are ignored by repository `.gitignore`.

## Post-download product gate

A task may be `completed` only if all are true:

- [ ] final file exists and `size > 0`.
- [ ] `LocalMetadataReader` can parse it.
- [ ] duration sanity does not show a material provider/local mismatch.
- [ ] file is indexed through the normal v0.4 Local Library pipeline.
- [ ] `local_audio_files.library_root_id` is non-NULL.
- [ ] `normalized_path` and structured metadata are present.
- [ ] downloaded file is visible through `LocalLibraryStorageRepository.list_tracks()`.
- [ ] exact provider/local identity link is persisted (`exact_id`).
- [ ] global Local Library fingerprint is computed after indexing so the exact automatic link is current.
- [ ] Coverage re-read returns `covered`.
- [ ] task is not completed when indexing/linking/Coverage refresh fails.
- [ ] no fuzzy candidate decision is needed for the known acquisition identity.
- [ ] no `Variant = SAME` result is fabricated by Download.

## Coverage behavior

- [ ] successful downloaded track leaves default Missing immediately after refresh.
- [ ] historical `wanted` may remain stored but no longer qualifies once Covered.
- [ ] failed/unavailable/auth/network task leaves Coverage Missing and user action wanted.
- [ ] ignored remains technical Missing but is never bulk-enqueued.
- [ ] Conflict / Not Analyzed truth-table semantics remain unchanged.
- [ ] strict v0.5.1 reference file alone still cannot establish Covered.

## Bridge / UI

- [ ] top-level navigation includes **Загрузки** after **Недостающие**.
- [ ] Missing + wanted row exposes **В загрузки**.
- [ ] needs_review/not_analyzed/covered rows do not expose ordinary Download.
- [ ] Downloads page shows queue/running/completed/error counters.
- [ ] filters All / queued / running / completed / errors work.
- [ ] target folder selection works and is persistent.
- [ ] bulk **Добавить все «Нужные»** works.
- [ ] **Запустить очередь** does not block Flutter rendering.
- [ ] active queue polling is bounded (~800 ms), not tens of polls per second.
- [ ] Retry and Cancel controls follow task capability.
- [ ] UI never displays token or direct URL.
- [ ] Flutter invokes Python with `runInShell: false`.

## Persistence / migration

- [ ] schema `1.7.0` extends existing `download_tasks`, not a parallel `download_tasks_v2`.
- [ ] `download_settings` persists the default target root.
- [ ] migration is idempotent.
- [ ] no database reset/manual SQL fix is required.
- [ ] Yandex cache/session data preserved.
- [ ] Local Library roots/files preserved.
- [ ] `matching_results`, `track_links`, `match_conflicts` preserved.
- [ ] manual accepts/rejects preserved.
- [ ] `track_variant_results` preserved.
- [ ] `provider_track_actions` wanted/ignored preserved.
- [ ] legacy download rows remain readable.
- [ ] `.musicark/musicark.db` is never required to be deleted.
- [ ] stored Yandex credential is never required to be deleted.

## Safety / privacy / Git audit

- [ ] diff contains no token, credentials, personal DB, real music, copyrighted audio fixture, or binary music fixture.
- [ ] no local existing file rename/move/delete/edit/transcode is introduced.
- [ ] no Yandex like/playlist/upload mutation is introduced.
- [ ] no YouTube/VK/torrent/pirate index/DRM bypass is introduced.
- [ ] local paths/library data are not sent to third parties beyond the selected provider request.
- [ ] direct provider URLs are ephemeral only.
- [ ] `.gitignore` protects common audio extensions from accidental manual-test commits.

## Manual Windows validation — mandatory before release acceptance

Start with 1–3 tracks:

- [ ] Yandex Library loaded.
- [ ] Local Library scanned.
- [ ] Matching run.
- [ ] one proven Missing row marked wanted.
- [ ] track added to Downloads.
- [ ] Local Library root selected.
- [ ] real progress displayed.
- [ ] download completed.
- [ ] physical final file exists and `.part` does not.
- [ ] file appears in Local Library.
- [ ] `library_root_id` is correct/non-NULL.
- [ ] exact provider/local link exists.
- [ ] track is Covered and disappears from default Missing.
- [ ] restart preserves completed history.
- [ ] network-off failure is recoverable.
- [ ] auth failure preserves queue and asks for re-authorization.
- [ ] unavailable track remains Missing with a clear failure.
- [ ] running Cancel leaves no corrupted final file and keeps Missing.

Then 5–10 tracks:

- [ ] bulk wanted enqueue creates no duplicate tasks.
- [ ] sequential/bounded worker remains responsive.
- [ ] no duplicate final files.
- [ ] no full Local Library rescan is performed after every completed file.
- [ ] each successful track becomes Covered independently.

Do not claim real Yandex download, Windows UI validation, performance, or full release readiness until these checks have actually run.
