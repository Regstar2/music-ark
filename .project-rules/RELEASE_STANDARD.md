# MusicArk release standard

## Release state

MusicArk is in feature freeze for the first public Windows release. v0.15.0 is the merged distribution baseline; v1.0.0 is release freeze and publication only.

## Required evidence

Before a stable release, record PASS / FAIL / NOT VERIFIED / N/A for:

- version consistency;
- full Python regression suite;
- Flutter analyze, tests and Windows build;
- v0.12 external metadata/network regressions;
- v0.13 multi-format/conversion regressions;
- v0.14 performance/database regressions;
- v0.15 update/feedback/packaging regressions;
- clean install, portable launch, reinstall, upgrade and uninstall;
- update failure/verification/confirmation behavior;
- RU/EN and Light/Dark/System smoke;
- feedback target accessibility;
- repository secret/privacy review;
- signing state.

A test is PASS only when executed against the recorded source/artifact. Historical evidence may be referenced but cannot silently substitute for current release-source validation.

## Artifacts

`scripts/release.ps1 -Version vX.Y.Z` must build final Windows artifacts into `dist/`.

Expected stable release set:

```text
MusicArk-X.Y.Z-win-x64.zip
MusicArk-Setup-X.Y.Z-x64.exe
SHA256SUMS.txt
update-manifest.json
```

The installer and ZIP must be generated from the same tagged source. SHA-256 values must be computed from actual artifacts.

## Publication

- Stable source tag is immutable.
- Release workflow runs CI again on the exact tag.
- Existing GitHub Releases are not overwritten silently.
- Signing state is stated factually: verified signed artifact or `UNSIGNED`.
- Public release notes must not claim tests/manual acceptance that were not performed.
- No credentials, Yandex account data, private library data, local paths or proxy secrets may be published.

## Feature freeze

Only release blockers may change before v1.0.0. New features and speculative refactors are deferred to a post-v1.0 roadmap.