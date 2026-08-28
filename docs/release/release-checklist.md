# Release Checklist — v1.0.0 Release Freeze

This checklist is the acceptance gate for the first public MusicArk Windows release. v0.15.0 is the distribution baseline and the later Windows acceptance fixes are merged; source history alone is not final release evidence.

Every gate against the final source/artifact must end as `PASS`, `FAIL`, `NOT VERIFIED`, or justified `N/A`.

## Source / release freeze

- [x] v1.0.0 feature freeze is respected; this finalization branch adds release blockers/docs only.
- [x] canonical source version is `1.0.0` in `VERSION`, Python and Flutter release metadata.
- [x] release-facing README RU/EN describes the v1.0 scope instead of an older development milestone.
- [x] v1.0.0 release notes exist at `docs/versions/v1.0.0.md`.
- [x] full RU/EN publication release notes exist at `docs/releases/v1.0.0.md` and `docs/releases/v1.0.0_EN.md`.
- [x] stable updater default points to the public MusicArk GitHub Release manifest path.
- [x] project `LICENSE` exists and identifies MusicArk's own code as MIT.
- [x] `THIRD_PARTY_NOTICES.md` and `licenses/` exist for redistributed runtime components.
- [ ] final source is reviewed through PR and trusted CI is green on the accepted PR head.
- [ ] final tag is exactly `v1.0.0` and points to the accepted source.
- [ ] no tag is moved after publication.

## Trusted GitHub automation

- [ ] `.github/workflows/trusted-ci.yml` is green on the final accepted source.
- [ ] external/fork PRs do not receive the self-hosted runner.
- [ ] owner same-repository PR runs `scripts/ci.ps1`.
- [ ] `.github/workflows/release.yml` starts from an existing trusted tag.
- [x] `.github/workflows/release.yml` is configured to run full `scripts/ci.ps1` against the exact tag before publishing.
- [x] `.github/workflows/release.yml` is configured to use prepared `docs/releases/v1.0.0-github.md` notes instead of fully generated notes.
- [ ] release workflow actually reruns source CI against the exact tag before publishing.

## Automated regression

Run from repository root:

```powershell
.\scripts\ci.ps1
```

- [ ] version consistency PASS.
- [ ] full Python suite PASS.
- [ ] external metadata/network regressions PASS.
- [ ] multi-format/conversion regressions PASS.
- [ ] large-library/performance/database regressions PASS.
- [ ] update/feedback/distribution regressions PASS.
- [ ] upload/recovery compatibility remains green through the full suite.
- [ ] `flutter analyze --no-fatal-infos` PASS.
- [ ] full `flutter test` PASS.
- [ ] Windows build/package smoke PASS.
- [ ] normal CI performs no live Yandex mutation.

Detailed mapping: `docs/testing/release-regression-matrix.md`.

## Final Windows artifacts

Run from the exact accepted source/tag through `scripts/release.ps1 -Version v1.0.0` or the trusted release workflow.

Required `dist/` files:

- [ ] `MusicArk-1.0.0-win-x64.zip`.
- [ ] `MusicArk-Setup-1.0.0-x64.exe`.
- [ ] `SHA256SUMS.txt`.
- [ ] `update-manifest.json`.
- [ ] `LICENSE`, `THIRD_PARTY_NOTICES.md` and `licenses/` are present in the portable ZIP.
- [ ] `LICENSE`, `THIRD_PARTY_NOTICES.md` and `licenses/` are present in the installer installation directory.
- [ ] installer and ZIP come from the same tagged source.
- [ ] SHA-256 values are computed from the actual final artifacts.
- [ ] update manifest references the exact final installer URL, byte size and SHA-256.

Do not copy hashes from an older RC into release notes.

## Windows acceptance

Issue #34 records that the owner already exercised installer/portable launch, packaged runtime without a development checkout, reinstall/uninstall data behavior, UI smoke and the distribution flow on the release candidate. That is valid acceptance evidence for the distribution design, but it does **not** replace a final artifact/link smoke after publication.

- [x] release-candidate Windows distribution acceptance recorded in #34.
- [ ] final `v1.0.0` installer launches after publication.
- [ ] final `v1.0.0` portable ZIP launches independently of a development checkout.
- [ ] final install/uninstall smoke preserves `%LOCALAPPDATA%\MusicArk` as designed.
- [ ] final RU/EN and core pages open from the published package.

## Update safety / public channel

- [x] default stable manifest location is `https://github.com/Regstar2/music-ark/releases/latest/download/update-manifest.json`.
- [x] endpoint remains overrideable with `MUSICARK_UPDATE_MANIFEST_URL` for testing/deployment.
- [x] manifest schema/channel/version validation remains strict.
- [x] update/redirect URLs are restricted to approved HTTPS GitHub/GitHubusercontent hosts.
- [x] redirects are bounded and each target is revalidated.
- [x] installer size and SHA-256 are checked exactly before prepare succeeds.
- [x] `check` is read-only; `prepare` does not launch; `apply` requires confirmation and re-verification.
- [ ] after repository publication, `releases/latest/download/update-manifest.json` is reachable without authentication.
- [ ] published manifest downloads the exact final installer and passes verification.

## Feedback / privacy / repository hygiene

- [ ] repository is switched from private to public only after all blocking source gates are resolved.
- [ ] Bug and Feature Issue Forms are reachable by an external/public user.
- [ ] tracked tree/history review finds no committed credentials, private user data, machine-specific secrets or packaged debug artifacts.
- [ ] final artifacts/logs contain no credentials or protected provider URLs.
- [ ] Project PAT or other automation credentials remain GitHub Actions secrets only.

## Legal / third-party / signing

- [x] owner has selected the intended project license and a correct root `LICENSE` exists: MIT, Copyright (c) 2026 Regstar2.
- [x] third-party notices/licenses for redistributed runtime components have been reviewed and included in source where required.
- [x] code-signing environment was checked locally: Windows SDK `signtool.exe` is present, but no suitable Authenticode certificate with private key was found.
- [x] installer signing state is stated factually in release notes as `UNSIGNED` for the checked environment.
- [ ] final unsigned/signed state is verified against the final published PE artifacts.

No project license is inferred automatically from dependency licenses, another repository, or a template. MusicArk's own-code license is now explicit; third-party components keep their own licenses.

## Publication

- [ ] accepted source is merged to `main`.
- [ ] exact annotated/release tag `v1.0.0` is created after acceptance.
- [ ] release workflow builds from that tag and creates a GitHub Release without overwriting an existing release.
- [ ] only final `dist/` files are attached.
- [ ] repository/release/download/update/feedback links are checked after public visibility is enabled.
- [ ] final post-publication Windows smoke is recorded.

If a blocking item is `FAIL` or `NOT VERIFIED`, do not publish stable v1.0.0 until the owner explicitly resolves or accepts that blocker.
