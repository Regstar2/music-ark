# Release Checklist — v0.6.0 Missing Tracks / Library Coverage

## Automated validation

- [ ] `python -m unittest discover -s tests -p "test_*.py" -v` is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] schema initializes twice without error and reports `1.6.0`.
- [ ] realistic `1.5.0 → 1.6.0` migration preserves Yandex cache, Local Library, v0.5 identity/manual/conflict data and v0.5.1 variant results.
- [ ] v0.5 Matching regression suite stays green.
- [ ] v0.5.1 Variant regression suite stays green.
- [ ] Coverage truth-table tests are green.
- [ ] reference-cache coverage regression is green.
- [ ] global collection dedup / scopes / playlist order tests are green.
- [ ] wanted/ignored/reset persistence and matching-change tests are green.
- [ ] bridge bulk IDs use structured payload and tests are green.
- [ ] Flutter Coverage navigation/summary/default-filter/scope/search/sort/pagination/triage/bulk/empty-state tests are green.

## Identity / coverage separation

- [ ] `MATCHED / CONFLICT / UNMATCHED` retain v0.5 semantics.
- [ ] current accepted `MATCHED` / manual accepted link → `covered`.
- [ ] current authoritative `UNMATCHED` with no accepted current link → `missing`.
- [ ] current `CONFLICT` → `needs_review`, never Missing.
- [ ] stale manual / invalid accepted link → `needs_review`.
- [ ] no matching result → `not_analyzed`, never Missing.
- [ ] stale automatic matcher/provider/Local Library state → `not_analyzed` until Matching reruns.
- [ ] `not matched == missing` shortcut does not exist.
- [ ] coverage status is derived, not stored in a `missing_tracks` copy table.

## Identity / variant separation

- [ ] identity confidence is stored/displayed separately from variant evidence.
- [ ] variant states remain `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, `NOT_CHECKED`.
- [ ] `MATCHED + SAME` → `covered / same`.
- [ ] `MATCHED + ALTERED` → `covered / altered`.
- [ ] `MATCHED + DIFFERENT_VERSION` → `covered / different_version`.
- [ ] `MATCHED + UNCERTAIN` → `covered / uncertain`.
- [ ] `MATCHED + NOT_CHECKED` → `covered / not_checked`.
- [ ] no variant state automatically changes accepted identity to Missing.
- [ ] no single combined identity+variant confidence is introduced.

## Active Yandex library / collections

- [ ] global identity is canonical `(provider_id, external_id)`.
- [ ] one track in Liked + multiple playlists counts once globally.
- [ ] playlist duplicate occurrence storage keys do not become fake provider identities.
- [ ] Liked and playlist scopes return correct totals/status counts.
- [ ] playlist scope preserves Yandex order.
- [ ] row/detail displays memberships.
- [ ] track removed from all active Yandex collections disappears from active Coverage.
- [ ] historical user action may remain stored but cannot create a zombie active Missing row.

## Coverage summary / performance

- [ ] `covered + missing + needs_review + not_analyzed = total`.
- [ ] Local coverage denominator is total unique provider identities in selected scope.
- [ ] Matching analyzed percentage is shown separately when Not Analyzed exists.
- [ ] variant summary is separate from primary coverage summary.
- [ ] summary/list/filter/search/sort/pagination are SQL-backed.
- [ ] no per-provider-track N+1 database loop is used for list pages.
- [ ] provider libraries in the 5k–20k range are paginated/lazy in Flutter.
- [ ] search covers title/artist/album/collection.

## User triage

- [ ] `provider_track_actions` stores only `wanted` / `ignored`; no row means `unreviewed`.
- [ ] per-track wanted/ignored/reset works.
- [ ] bulk wanted/ignored/reset works.
- [ ] decisions persist across restart.
- [ ] ignored remains technically Missing and can be filtered.
- [ ] a historical wanted action on a later Covered track no longer qualifies for `missing + wanted`.
- [ ] no Download button/queue execution exists in v0.6 Coverage.

## Reference audio

- [ ] resolver accepts strict `yandex_<id>.<ext>`.
- [ ] resolver accepts strict `yandex-<id>.<ext>`.
- [ ] incidental numbers in paths are rejected.
- [ ] explicit single-track v0.5.1 verification may use the existing bounded exact-reference acquisition when needed.
- [ ] `variant_run_all_available` remains bounded and does not silently download the library.
- [ ] acquired/cached reference is not inserted into Local Library.
- [ ] acquired/cached reference does not create `track_links`.
- [ ] `reference exists + no accepted local link + current UNMATCHED → MISSING`.
- [ ] reference files are never modified by Coverage.

## v0.5.1 metadata / audio regression

- [ ] semantic markers include Live, Remix/Mix, Acoustic, Instrumental, Remaster(ed), Radio Edit/Version, Edit, Extended, Demo, Clean, Explicit, Censored, Uncensored.
- [ ] provider `content_warning → explicit` remains variant evidence only.
- [ ] explicit mismatch alone never proves censored/uncensored.
- [ ] `AudioDecoder` abstraction remains failure-safe.
- [ ] decoded target remains fixed mono signed-16 PCM sample rate.
- [ ] PCM is piped/in-memory rather than persisted as giant WAV/audio blobs.
- [ ] MP3/FLAC byte SHA equality is not used as same-recording proof.
- [ ] alignment remains bounded.
- [ ] neighboring low-similarity windows merge into altered regions.
- [ ] technical error never becomes `DIFFERENT_VERSION`.
- [ ] false-positive `SAME` remains worse than `UNCERTAIN`.
- [ ] unchanged successful variant pair skips redundant decode.
- [ ] local/reference/provider/analyzer changes invalidate variant cache on verification rerun.

## Bridge / UI

- [ ] bridge includes `coverage_summary`, `coverage_tracks`, `coverage_track`, `coverage_collections`, `coverage_set_action`, `coverage_set_actions`.
- [ ] bulk IDs are transported as structured JSON, not concatenated into a shell command.
- [ ] Flutter launches Python with `runInShell: false`.
- [ ] top-level navigation includes **Недостающие**.
- [ ] default Coverage filter is Missing.
- [ ] Missing / Needs Review / Not Analyzed / Covered rows have distinct presentation.
- [ ] Covered variant warning is secondary.
- [ ] Needs Review / Not Analyzed can route into existing Matching.
- [ ] matching candidate/detail UI is not reimplemented inside Coverage.
- [ ] pagination/lazy list avoids creating thousands of row widgets simultaneously.

## Persistence / migration

- [ ] schema `1.6.0` adds only `provider_track_actions` and required index(es).
- [ ] no database reset/manual SQL fix is required.
- [ ] Yandex cache/session data preserved.
- [ ] Local Library roots/files preserved.
- [ ] `matching_results`, `track_links`, `match_conflicts` preserved.
- [ ] manual accepts/rejects preserved.
- [ ] `track_variant_results` preserved.
- [ ] `.musicark/musicark.db` is never required to be deleted.
- [ ] stored Yandex credential is never required to be deleted.

## Safety / privacy / secrets

- [ ] diff contains no token, credentials, personal DB, real music, copyrighted audio fixture, or binary music fixture.
- [ ] no local file rename/move/delete/edit/transcode is introduced.
- [ ] no Yandex like/playlist/upload mutation is introduced.
- [ ] no external matching/metadata/fingerprint/coverage analytics API is introduced.
- [ ] no Missing Tracks download/source-selection execution is introduced.
- [ ] local paths/matching/missing-list data are not sent to third-party services.

## Manual Windows validation

- [ ] Yandex Library loaded and Local Library scanned.
- [ ] Matching completed.
- [ ] Coverage summary agrees with Matching source state.
- [ ] UNMATCHED is Missing.
- [ ] CONFLICT is not Missing.
- [ ] Not Analyzed is not Missing.
- [ ] MATCHED + DIFFERENT_VERSION remains Covered with warning.
- [ ] several Missing rows marked wanted.
- [ ] several Missing rows marked ignored.
- [ ] restart preserves decisions.
- [ ] rerun Matching moves newly matched row out of Missing.
- [ ] Liked/playlist filters and playlist order work.
- [ ] offline Coverage works.
- [ ] strict v0.5.1 reference without accepted Local Library link does not count as Covered.
- [ ] v0.5.1 same/altered/different-version/ffmpeg regressions remain acceptable on controlled fixtures.

Do not claim real-library Coverage correctness, performance, Windows UI validation, or full test-suite success until those checks have actually run.
