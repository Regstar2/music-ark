# Release Checklist — v0.5.1 Variant / Altered Track Detection

## Automated — local only

Do not use GitHub Actions for this milestone.

- [ ] `python -m unittest discover -s tests -v` is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] schema initializes twice without error and reports `1.5.0`.
- [ ] `1.4.0 → 1.5.0` migration preserves Yandex cache, Local Library, v0.5 matching results, track links/conflicts and manual decisions.
- [ ] v0.5 matching regression suite stays green.
- [ ] synthetic identical/copy-like audio is `SAME`.
- [ ] localized silence/tone replacement can be `ALTERED`.
- [ ] substantial difference is never forced to `SAME`.
- [ ] bounded start-offset alignment regression is green.
- [ ] semantic variant marker tests are green.
- [ ] explicit mismatch without audio does not claim censorship.
- [ ] missing reference/decoder/corrupt input fail gracefully.
- [ ] cache reuse and local/reference invalidation tests are green.
- [ ] Flutter variant badge/detail/progress/error/refresh widget tests are green.

## Identity / variant separation

- [ ] `MATCHED / CONFLICT / UNMATCHED` retain v0.5 semantics.
- [ ] identity confidence is stored/displayed separately from variant evidence.
- [ ] variant states are exactly represented as `SAME`, `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, `NOT_CHECKED`.
- [ ] no single combined identity+variant confidence is introduced.
- [ ] audio verification is never run for ordinary unresolved `UNMATCHED`/`CONFLICT` rows.
- [ ] manually accepted identity links are eligible for variant verification.

## Metadata variant policy

- [ ] title/artists/album/duration/explicit/filename evidence is available.
- [ ] semantic markers include Live, Remix/Mix, Acoustic, Instrumental, Remaster(ed), Radio Edit/Version, Edit, Extended, Demo, Clean, Explicit, Censored, Uncensored.
- [ ] semantic marker extraction is separate from identity normalization.
- [ ] provider `content_warning → explicit` is used as variant evidence.
- [ ] explicit mismatch alone never proves censored/uncensored.
- [ ] provider variant fingerprint includes variant-relevant metadata and explicit state.

## Reference audio

- [ ] resolver accepts strict `yandex_<id>.<ext>`.
- [ ] resolver accepts strict `yandex-<id>.<ext>`.
- [ ] incidental numbers in paths are rejected.
- [ ] resolver is a separate component, not duplicated throughout matching.
- [ ] no automatic reference download occurs.
- [ ] reference files are never modified.

## Audio decoder / comparison

- [ ] `AudioDecoder` abstraction exists.
- [ ] `FfmpegAudioDecoder` is optional and failure-safe.
- [ ] decoded target is one fixed mono signed-16 PCM sample rate.
- [ ] PCM is piped/in-memory rather than persisted as giant WAV fixtures.
- [ ] MP3/FLAC byte SHA equality is not used as same-recording proof.
- [ ] alignment is bounded (no unrestricted collection-wide dynamic alignment).
- [ ] segment window/hop and thresholds live in policy/config constants.
- [ ] similarity has volume/encoding robustness and spectral evidence.
- [ ] neighboring low-similarity windows merge into altered regions.
- [ ] isolated mild outliers are suppressed.
- [ ] each region has start/end/mean/minimum similarity.

## Classification policy

- [ ] `SAME` requires strong compatible metadata/audio evidence.
- [ ] `ALTERED` requires high global recording consistency plus localized persistent divergence.
- [ ] obvious semantic/duration/distributed differences are not labeled `SAME`.
- [ ] near-boundary/conflicting evidence becomes `UNCERTAIN`.
- [ ] technical error never becomes `DIFFERENT_VERSION`.
- [ ] `possible_clean_or_censored_variant` requires several agreeing signals and is presented as possible, not certain.
- [ ] false-positive `SAME` is treated as worse than `UNCERTAIN`.

## Persistence / invalidation

- [ ] `track_variant_results` uses `(provider_id, external_id, local_file_id)` identity.
- [ ] no PCM/audio blob is stored in SQLite.
- [ ] provider/local/reference fingerprints are stored.
- [ ] analyzer version is stored.
- [ ] unchanged successful pair skips redundant decode.
- [ ] local file size/mtime change invalidates result.
- [ ] reference size/mtime change invalidates result.
- [ ] provider variant metadata change invalidates result.
- [ ] analyzer version change invalidates result.
- [ ] technical failure does not become a permanently sticky cache result.

## Performance / batch

- [ ] there is no decode loop across the entire Local Library for every Yandex track.
- [ ] batch starts from v0.5 matched pairs only.
- [ ] batch further limits deep audio work to pairs with exact references.
- [ ] one file failure does not abort all remaining pairs.
- [ ] Flutter does not receive PCM through the bridge.
- [ ] Flutter shows a progress/busy state while Python-side batch work runs.

## UI / bridge

- [ ] matched row shows identity and secondary variant badges separately.
- [ ] detail shows separate Identity and Variant verification sections.
- [ ] audio similarity and altered regions are visible when available.
- [ ] `Проверить версию` works for a matched row.
- [ ] `Проверить все доступные` works in a controlled batch.
- [ ] missing ffmpeg is explicit in the UI.
- [ ] bridge includes `variant_capabilities`, `variant_summary`, `variant_run`, `variant_run_all_available`, `variant_result`, `variant_results`.
- [ ] `matching_run` is not overloaded with PCM/audio work.

## Safety / privacy / secrets

- [ ] diff contains no token, credentials, personal DB, real music, copyrighted audio fixture, or binary music fixture.
- [ ] no local file rename/move/delete/edit/transcode is introduced.
- [ ] no Yandex like/playlist/upload mutation is introduced.
- [ ] no external matching/metadata/fingerprint API is introduced.
- [ ] no automatic reference-track download is introduced.
- [ ] `.musicark/musicark.db` is never required to be deleted.
- [ ] stored Yandex credential is never required to be deleted.

## Manual Windows validation

- [ ] same recording MP3 ↔ FLAC.
- [ ] same recording with volume/encoding change.
- [ ] clean/explicit pair if legally available.
- [ ] Radio Edit.
- [ ] Live version.
- [ ] Remix.
- [ ] copied test/owned audio with short silence replacement.
- [ ] copied test/owned audio with short tone/noise replacement.
- [ ] small leading-offset alignment.
- [ ] ffmpeg unavailable path.
- [ ] corrupt/missing test file does not stop batch.
- [ ] restart confirms variant result persistence.
- [ ] v0.5 manual accept remains intact.

Do not claim real-library variant quality or censorship detection is validated until the Windows/manual review has actually been completed.
