# Release Checklist — v0.8.0 Controlled Sync

## Automated

- [ ] full Python unittest discovery is green.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` is green.
- [ ] `flutter test` is green.
- [ ] realistic `1.7.0 → 1.8.0` migration preserves modern data and legacy sync rows.
- [ ] repeated initialization is idempotent.

## Planning

- [ ] all / liked / playlist scopes use active cached Yandex membership.
- [ ] provider identities and duplicate playlist occurrences are deduplicated.
- [ ] Covered creates no download operation.
- [ ] Missing+Wanted creates `ENQUEUE_DOWNLOAD` only.
- [ ] Missing+Unreviewed creates a decision blocker.
- [ ] Missing+Ignored creates no download.
- [ ] Needs Review / Not Analyzed remain matching blockers.
- [ ] UNCERTAIN/ALTERED/DIFFERENT_VERSION are Variant review only.
- [ ] planner performs no download, matching run, variant run, filesystem mutation or Yandex mutation.
- [ ] covered rows are summarized rather than persisted as thousands of NOOPs.

## Staleness / race safety

- [ ] active Yandex membership change makes planned plan stale.
- [ ] Local Library fingerprint change makes planned plan stale.
- [ ] matching/triage change makes planned plan stale.
- [ ] exact download target change makes planned plan stale.
- [ ] playback state does not affect fingerprint.
- [ ] stale Apply is disabled/refused.
- [ ] execution-time recheck skips an identity that became Covered/not-Wanted.

## Apply

- [ ] explicit confirmation is mandatory.
- [ ] no target → preview allowed, Apply refused.
- [ ] Apply delegates to v0.7 `DownloadService.enqueue()`.
- [ ] Apply never calls legacy `DownloadSystem`.
- [ ] Apply never drains/runs the global download queue.
- [ ] active queued/running identity is not duplicated.
- [ ] repeated Apply is idempotent.
- [ ] operation task ids/results and applied result persist.
- [ ] partial blockers do not prevent safe Missing+Wanted enqueue, but UI shows them.

## Legacy / safety

- [ ] old sync plans remain readable after migration.
- [ ] legacy upload/replace/metadata candidates cannot execute in v0.8.
- [ ] local-only/outside-scope files are informational only.
- [ ] local delete/move/rename/tag edit count is zero.
- [ ] Yandex like/playlist/upload/replace mutation count is zero.
- [ ] no token/auth header/direct URL is persisted in sync tables, UI, logs or audit.

## Flutter

- [ ] navigation includes **Синхронизация** after **Загрузки**.
- [ ] scope selector and exact target state render.
- [ ] create-plan dry run/summary/current-vs-projected render.
- [ ] download/decision/identity/matching/variant/local-only groups render.
- [ ] stale and legacy banners render.
- [ ] confirmation/result/open Downloads work.
- [ ] review links open Matching.
- [ ] history and cancel-plan work.
- [ ] no-target state disables Apply.

## Manual Windows acceptance

Complete every scenario in `docs/testing/manual-test-plan.md`, beginning with a small controlled dataset. Do not claim full release readiness until real Windows validation has run.
