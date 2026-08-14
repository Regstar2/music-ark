# Release Checklist — v0.5.0 Matching

## Automated

- [ ] `python -m unittest discover -s tests -v` is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] schema initializes twice without error and reports `1.4.0`.
- [ ] v0.4 → v0.5 migration preserves Yandex collection cache and Local Library rows.
- [ ] normalization/scoring/ambiguity tests are green.
- [ ] scale regression proves detailed comparisons stay bounded and do not form the full Cartesian product.
- [ ] duplicate Liked/playlist membership materializes one provider identity.
- [ ] manual accept/reject persistence tests are green.
- [ ] deleted-local-file invalidation test is green.

## Matching policy

- [ ] automatic threshold is centralized (`>= 0.90`).
- [ ] conflict threshold is centralized (`>= 0.70`).
- [ ] best-vs-second ambiguity margin is centralized (`>= 0.04` for auto-match).
- [ ] score breakdown includes title/artists/duration/album and final confidence.
- [ ] semantic markers such as live/remix/acoustic/instrumental are not blindly removed.
- [ ] filename is fallback below structured metadata.
- [ ] exact Yandex-ID heuristic only accepts the strict filename convention.

## Architecture / performance

- [ ] production matcher contains no `for yandex in all × for local in all` algorithm.
- [ ] candidate queries use normalized title / artist / duration indexes.
- [ ] detailed candidate count is bounded.
- [ ] matching writes use batch transactions rather than one transaction per provider track.
- [ ] results API supports `limit`, `offset`, `status`, `search`, and sort.
- [ ] matcher version and input fingerprints are stored.

## Manual decisions

- [ ] conflict detail shows multiple candidates when present.
- [ ] manual accept creates a `manual` link.
- [ ] automatic rerun does not overwrite a manual link.
- [ ] manual reject persists.
- [ ] rejected candidate does not immediately return as the active best candidate.
- [ ] another candidate can be selected after rejection.

## Regression

- [ ] Yandex saved session restores.
- [ ] Liked and playlists still load/refresh/cache offline.
- [ ] Local Library roots, scan, incremental rescan, search, sort and details still work.
- [ ] matching a track appearing in multiple Yandex collections creates one result.
- [ ] Local Library rescan can invalidate/recalculate affected automatic results.

## Safety / privacy / secrets

- [ ] diff contains no token, credentials, personal music paths, DB files, or binary music fixtures.
- [ ] matching does not rename/move/delete/edit/transcode local audio files.
- [ ] matching does not mutate likes/playlists/uploads in Yandex Music.
- [ ] matching has no external matching/metadata API dependency.
- [ ] `.musicark/musicark.db` is never required to be deleted for upgrade.
- [ ] stored Yandex credential is never required to be deleted.

## Manual Windows validation

- [ ] run against Yandex Library + `C:\MusicArk-Test` or existing test library.
- [ ] inspect at least 10 obvious matches.
- [ ] inspect at least 5 difficult matches.
- [ ] inspect live/remix/acoustic and same-title/different-artist cases.
- [ ] test one manual accept across restart.
- [ ] test one manual reject across rerun.
- [ ] verify matching still runs with network disconnected after caches are populated.
- [ ] record false positives, if any, before accepting thresholds.

Do not claim real-library matching quality is validated until this Windows/manual review has actually been completed.
