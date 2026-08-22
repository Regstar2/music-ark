# Release Checklist — v0.15.0 Distribution Candidate

This checklist is the acceptance gate for the v0.15.0 Draft PR. It does **not** imply a tag, GitHub Release, published stable manifest, public installer, repository visibility change, or v1.0.0 release.

## Version / schema / Git

- [ ] `VERSION` contains `0.15.0`.
- [ ] Python package/backend versions are `0.15.0`.
- [ ] Flutter version is `0.15.0+1` and `AppInfo.version/backendVersion` are `0.15.0`.
- [ ] `tools/check_version_consistency.py` passes.
- [ ] core SQLite schema remains `1.9.0`.
- [ ] branch is based on merged v0.14.0 `main`.
- [ ] Draft PR targets `main` and is not auto-merged.
- [ ] final diff contains no credentials, user library data, packaged binaries or unrelated mass formatting.

## Standalone Windows runtime

- [ ] release app starts without a system Python installation.
- [ ] release app starts without a source checkout or development `.venv`.
- [ ] frozen runtime accepts only approved MusicArk bridge modules.
- [ ] packaged compatibility sentinels contain no user/project source data used as runtime truth.
- [ ] packaged backend redirects mutable `--base-dir` state to the per-user data root.
- [ ] installed program directory remains free of user database/configuration writes during normal use.
- [ ] FFmpeg/Yandex/keyring/runtime dependencies needed by production bridges are present in the frozen package.

## Packaging

- [ ] `tools/package_windows.ps1 -SkipInstaller` creates a standalone portable ZIP.
- [ ] packaged runtime `--version` smoke succeeds.
- [ ] packaged feedback bridge smoke succeeds.
- [ ] `SHA256SUMS.txt` is generated from actual output files.
- [ ] Inno Setup installer compiles from `packaging/windows/MusicArk.iss` on a machine with Inno Setup 6.
- [ ] installer uses stable AppId for in-place upgrade.
- [ ] installer is per-user and does not require elevation for normal installation.
- [ ] install → launch works on a clean Windows user profile.
- [ ] reinstall/upgrade over the same version does not destroy MusicArk data.
- [ ] upgrade from the previous accepted build preserves MusicArk data and credentials.
- [ ] uninstall removes program files but preserves `%LOCALAPPDATA%\MusicArk` user data.
- [ ] uninstall does not silently remove Cloudflare WARP or other external software.
- [ ] portable ZIP starts independently of the development checkout.

## Auto-update safety

- [ ] manifest schema/version/channel validation is strict.
- [ ] version comparison uses strict `MAJOR.MINOR.PATCH` values.
- [ ] manifest and redirect URLs require approved HTTPS GitHub/GitHubusercontent hosts.
- [ ] redirect count is bounded and every target is revalidated.
- [ ] installer file name is a plain `.exe` name.
- [ ] installer byte size is checked exactly.
- [ ] installer SHA-256 is checked exactly before promotion/use.
- [ ] failed/hash-mismatched downloads never become prepared installers.
- [ ] `check` is read-only.
- [ ] `prepare` downloads/verifies but does not launch.
- [ ] `apply` requires explicit user confirmation and re-verifies the prepared installer.
- [ ] update/network failure does not prevent the app or Settings from opening.
- [ ] no token/cookie/provider credential is sent to the update channel.
- [ ] `tools/generate_update_manifest.py` produces hash/size from a real installer.
- [ ] no stable manifest is published by this PR.

## Feedback / privacy

- [ ] Bug and Feature actions are available from Settings.
- [ ] GitHub Issue Forms exist for both actions.
- [ ] feedback target can be switched at deployment time without changing product logic.
- [ ] automatic bug diagnostics contain only MusicArk version, OS and architecture.
- [ ] diagnostics do not contain Yandex tokens/cookies, signed URLs, account identifiers, proxy secrets, filesystem music paths or library contents.
- [ ] user is told to review report contents before submission.
- [ ] browser-open failure has a usable copied-link fallback.

## WARP ownership boundary

- [ ] existing v0.12 ownership state remains readable.
- [ ] MusicArk uninstall does not silently uninstall WARP.
- [ ] WARP management remains explicit in Settings.
- [ ] no update/installer path disables TLS verification or bypasses existing proxy/network policy.

## Regression safety

Ordinary v0.15 distribution work must preserve:

```text
new Matching semantics = 0
new Variant semantics = 0
new Coverage semantics = 0
new Download semantics = 0
new Sync semantics = 0
new Metadata write semantics = 0
new Yandex mutation semantics = 0
existing user audio silently modified/deleted = 0
```

- [ ] v0.12 external-network routing remains separate from Yandex upload semantics.
- [ ] v0.13 source-safe conversion remains unchanged.
- [ ] v0.14 cache-first/performance behavior remains unchanged.

## Automated checks

From repository root:

- [ ] full `python -m unittest discover -s tests -p "test_*.py" -v`.
- [ ] `python tools/check_version_consistency.py`.
- [ ] `python -m unittest tests.test_v015_distribution -v`.
- [ ] existing v0.12/v0.13/v0.14 and upload/recovery regressions remain green.

From `ui/musicark_ui`:

- [ ] `flutter pub get`.
- [ ] `flutter analyze --no-fatal-infos`.
- [ ] `flutter test test/v015_distribution_test.dart`.
- [ ] full `flutter test`.
- [ ] `flutter build windows`.

CI:

- [ ] `Tests` workflow result recorded from final PR head.
- [ ] `v0.15 Distribution / distribution-contract` recorded from final PR head.
- [ ] `v0.15 Distribution / distribution-ui` recorded from final PR head.
- [ ] `v0.15 Distribution / standalone-package-smoke` recorded from final PR head.
- [ ] produced CI package artifact inspected for expected files.

## Manual Windows acceptance

- [ ] development run still works.
- [ ] standalone packaged build starts.
- [ ] Settings opens while update endpoint is unavailable.
- [ ] current/latest/check UI works in RU and EN.
- [ ] prepared installer cannot launch without confirmation.
- [ ] Bug/Feature actions open the expected GitHub forms or copy the fallback link.
- [ ] Light/Dark/System and normal/narrow desktop layouts remain usable.
- [ ] Yandex / Local / Matching / Missing / Downloads / Sync / Metadata Editor still open and preserve prior behavior.

## Signing / publication

- [ ] signing state is stated factually: signed with verified certificate or **UNSIGNED**.
- [ ] if signed, signature is verified on the exact installer/EXE artifacts.
- [ ] if unsigned, release notes do not imply trusted code signing.
- [ ] public update/feedback channel is configured before v1.0 public release.
- [ ] final v1.0 artifacts/manifest are published only after clean-install/upgrade validation.

If a tool or environment is unavailable, mark the gate **NOT VERIFIED** rather than passed. Keep the PR Draft until owner acceptance. Do not merge automatically.
