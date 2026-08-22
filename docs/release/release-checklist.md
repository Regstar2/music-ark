# Release Checklist — v1.0.0 Release Freeze

This checklist is the acceptance gate for the first public MusicArk Windows release. v0.15.0 is the merged distribution baseline; merge history alone is not release evidence.

Every item must end as `PASS`, `FAIL`, `NOT VERIFIED`, or justified `N/A` against the final release source/artifact.

## Process / source

- [ ] Issues #32–#35 are triaged in the shared Development Project.
- [ ] v1.0.0 feature freeze is respected; no new product scope is added.
- [ ] final source is reviewed through PR and trusted CI.
- [ ] `VERSION`, Python and Flutter versions agree.
- [ ] final release tag is exactly `v1.0.0` and points to accepted source.
- [ ] no tag is moved after publication.

## Trusted GitHub automation

- [ ] `.github/workflows/trusted-ci.yml` is active from `main`.
- [ ] external/fork PR does not receive the self-hosted runner.
- [ ] owner same-repository PR runs `scripts/ci.ps1`.
- [ ] `.github/workflows/project-sync.yml` adds owner Issues to Project #2.
- [ ] `.github/workflows/release.yml` works only from an existing trusted tag.
- [ ] legacy unrestricted self-hosted PR workflows are removed after bootstrap.

## Automated release regression

Run from repository root:

```powershell
.\scripts\ci.ps1
```

- [ ] version consistency PASS.
- [ ] full Python suite PASS.
- [ ] v0.12 external metadata/network regressions PASS.
- [ ] v0.13 multi-format/conversion regressions PASS.
- [ ] v0.14 performance/database regressions PASS.
- [ ] v0.15 update/feedback/distribution regressions PASS.
- [ ] v0.11.x upload/recovery compatibility remains green through the full suite.
- [ ] `flutter analyze --no-fatal-infos` PASS.
- [ ] full `flutter test` PASS.
- [ ] `flutter build windows` PASS.
- [ ] deterministic performance and SQLite audit reports are retained.
- [ ] portable standalone package smoke PASS.
- [ ] normal CI performs no live Yandex mutation.

Detailed mapping: `docs/testing/release-regression-matrix.md`.

## Final Windows artifacts

Run from the exact release source/tag through `scripts/release.ps1` / release workflow.

Required `dist/` files:

- [ ] `MusicArk-1.0.0-win-x64.zip`.
- [ ] `MusicArk-Setup-1.0.0-x64.exe`.
- [ ] `SHA256SUMS.txt`.
- [ ] `update-manifest.json`.
- [ ] installer and ZIP come from the same tagged source.
- [ ] SHA-256 values are computed from actual final artifacts.
- [ ] update manifest references the exact final installer size/hash.

## Manual Windows acceptance

Tracked by Issue #34.

- [ ] clean install under a fresh Windows user profile.
- [ ] installed app launches without system Python and without source checkout.
- [ ] portable ZIP launches independently of development checkout.
- [ ] reinstall same version preserves `%LOCALAPPDATA%\MusicArk`.
- [ ] upgrade from previous accepted build preserves DB/config/credentials.
- [ ] uninstall removes program files but preserves MusicArk user data.
- [ ] uninstall does not silently remove Cloudflare WARP or other external software.
- [ ] unavailable update endpoint does not block app startup or Settings.
- [ ] prepared installer cannot launch without explicit confirmation.
- [ ] Yandex / Local / Matching / Missing / Downloads / Sync / Metadata Editor open after packaging.
- [ ] RU/EN smoke PASS.
- [ ] Light/Dark/System and normal/narrow desktop smoke PASS.

## Update safety

- [ ] manifest schema/channel/version validation remains strict.
- [ ] update/redirect URLs remain approved HTTPS GitHub/GitHubusercontent hosts.
- [ ] redirect count is bounded and every target is revalidated.
- [ ] installer file name is a plain `.exe` name.
- [ ] installer size and SHA-256 are checked exactly.
- [ ] failed/hash-mismatched downloads are never promoted.
- [ ] `check` is read-only.
- [ ] `prepare` downloads/verifies but does not launch.
- [ ] `apply` requires explicit user confirmation and re-verifies.
- [ ] update failure does not prevent normal application use.
- [ ] update traffic sends no Yandex/provider/proxy credentials.

## Feedback / privacy / security

- [ ] Bug and Feature actions work against the intended public tracker.
- [ ] Issue Forms are available after repository publication.
- [ ] diagnostics contain no tokens/cookies/signed URLs/account identifiers/proxy secrets/music paths/library contents.
- [ ] repository history/current tree review finds no committed credentials or private user data.
- [ ] generated artifacts/logs do not expose secrets.
- [ ] Project PAT remains only in GitHub Actions secret `ADD_TO_PROJECT_PAT`.

## README / legal / publication

Tracked by Issue #35.

- [ ] README.md and README_EN.md match actual v1.0 scope and limitations.
- [ ] install/update/feedback instructions match final public URLs.
- [ ] LICENSE exists and is correct for the intended public release.
- [ ] third-party notices/licenses are reviewed where required.
- [ ] changelog/release notes describe merged facts only.
- [ ] signing state is stated factually: verified signed artifacts or `UNSIGNED`.
- [ ] no claim of PASS is based only on historical CI from an older head.

## Publication

- [ ] exact `v1.0.0` tag created only after acceptance.
- [ ] release workflow reruns CI on the exact tag.
- [ ] release workflow creates GitHub Release without overwriting an existing release.
- [ ] only final files from `dist/` are attached.
- [ ] release page/download/update/feedback links are checked after repository publication.

If a blocking item is `FAIL` or `NOT VERIFIED`, do not publish a stable v1.0.0 release until the owner explicitly resolves or accepts the blocker.