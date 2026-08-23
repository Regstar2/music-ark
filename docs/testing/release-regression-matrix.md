# MusicArk release regression matrix — v0.12 to v0.15

This matrix is the automated/manual evidence plan for the v1.0.0 release freeze. A check is `PASS` only after it runs against the recorded source or final artifact. If the environment is unavailable, record `NOT VERIFIED`.

## One-command automated gate

From repository root on the trusted Windows runner:

```powershell
.\scripts\ci.ps1
```

The script requires Python 3.12 and Flutter, removes live Yandex mutation environment variables, runs the full Python/Flutter regression suites, performance evidence and a portable package smoke.

---

## Baseline — all versions

| Check | Command / evidence | Type | Release state |
|---|---|---|---|
| Version consistency | `py -3.12 tools/check_version_consistency.py` | Automated | pending current PR |
| Full Python suite | `py -3.12 -m unittest discover -s tests -p "test_*.py" -v` | Automated | pending current PR |
| Flutter dependencies | `flutter pub get` | Automated | pending current PR |
| Flutter analyzer | `flutter analyze --no-fatal-infos` | Automated | pending current PR |
| Full Flutter suite | `flutter test` | Automated | pending current PR |
| Windows Flutter build | `flutter build windows` | Automated | pending current PR |
| Portable package smoke | `tools/package_windows.ps1 -SkipInstaller -PythonVersion 3.12` | Automated | pending current PR |
| Real Yandex mutation | separate explicit owner procedure only | Manual/live | NOT VERIFIED by normal CI |

Normal CI must not use `YANDEX_MUSIC_TOKEN`, `MUSICARK_YANDEX_UPLOAD_LIVE` or `MUSICARK_YANDEX_PLAYLIST_LIVE`.

---

## v0.12 — External Metadata & Resilient Network Access

### Automated backend regressions

Existing focused files:

```text
tests/test_acoustid_metadata_v012.py
tests/test_external_credentials_builtin_v012.py
tests/test_external_lookup_cleanup_v012.py
tests/test_external_metadata_v012.py
tests/test_external_yandex_fallback_v012.py
tests/test_fpcalc_provisioning_v012.py
tests/test_warp_v012.py
tests/test_yandex_first_resolver_v012.py
```

Required behavior:

- Yandex-first metadata resolution remains the fast path;
- title/artist lookup cleanup removes distribution noise without deleting semantic markers;
- AcoustID/fpcalc is rescue, not an unconditional request;
- external metadata source credentials are not leaked;
- fpcalc provisioning and fingerprint failures fail safely;
- Direct / HTTP(S) / SOCKS5 / WARP / Auto routing keeps the configured network boundary;
- WARP ownership and fail-closed behavior remain intact;
- no provider failure enables a live mutation as fallback.

### Flutter regression

```text
ui/musicark_ui/test/v012_external_metadata_ui_test.dart
```

### Manual release smoke

- proxy modes can be selected/configured without exposing credentials;
- unavailable external metadata sources do not block Local Library;
- WARP management remains explicit and does not become an uninstall side effect.

---

## v0.13 — Multi-Format Audio & Safe Yandex Conversion

### Automated backend regression

Primary focused file:

```text
tests/test_v013_multiformat_conversion.py
```

Also keep upload/conversion interaction protected by the full suite, including production upload service regressions.

Required behavior:

- supported format capability routing remains explicit;
- MP3/MP4/Vorbis/generic metadata adapters preserve format boundaries;
- FFmpeg executable resolution is deterministic;
- conversion creates a derivative instead of rewriting the source audio;
- temporary conversion artifacts are removed through success/failure paths;
- unsupported/unsafe formats fail closed;
- Yandex upload receives the converted derivative only where conversion is required;
- original local audio is never silently deleted or modified.

### Manual release smoke

Use representative owned test files for the formats actually claimed in README/docs and verify metadata read/edit + upload conversion without changing the source file.

---

## v0.14 — Large Library Performance & Release Hardening

### Automated backend regression

```text
tests/test_v014_performance_hardening.py
```

Additional deterministic evidence:

```powershell
py -3.12 .\tools\performance_smoke.py --output .\.musicark\performance\release-regression.json
py -3.12 .\tools\sqlite_query_audit.py --output .\.musicark\performance\sqlite-query-audit.json
```

Required behavior:

- Local Library activation is cache-first;
- recursive scan remains explicit;
- backend pagination is bounded;
- missing-path delta does not rewrite every unchanged row;
- artwork batch lookup avoids per-row database connection/query behavior;
- no-cover artwork negative cache is invalidated when source/provider identity changes;
- 1k/10k/50k synthetic report completes without an unbounded materialization regression;
- audited SQLite hot-query plans remain acceptable.

### Flutter regression

```text
ui/musicark_ui/test/v014_performance_hardening_test.dart
```

### Manual release smoke

On a real several-thousand-track collection verify startup/navigation responsiveness, explicit Scan behavior, search/sort/pagination and memory behavior. Record collection size and machine used; do not publish private library listings.

---

## v0.15 — Installer, Auto-Update, Feedback & Packaging

### Automated backend regression

```text
tests/test_v015_distribution.py
```

Required behavior:

- all version sources agree with `VERSION`;
- frozen runtime dispatcher accepts only approved MusicArk bridge modules;
- feedback diagnostics contain only safe fields;
- update manifest parser validates schema/channel/version;
- update URLs remain HTTPS and limited to approved GitHub/GitHubusercontent hosts;
- redirects are bounded and each redirect is revalidated;
- installer name/size/SHA-256 are checked exactly;
- `check` is read-only;
- `prepare` never launches;
- `apply` requires explicit confirmation and re-verifies the installer;
- network/update failure does not prevent application startup/Settings.

### Flutter regression

```text
ui/musicark_ui/test/v015_distribution_test.dart
ui/musicark_ui/test/utility_pages_test.dart
```

### Automated package smoke

`tools/package_windows.ps1 -SkipInstaller` must produce:

```text
MusicArk-<version>-win-x64.zip
SHA256SUMS.txt
```

and the staged Flutter executable must be named `Music Ark.exe`. The packaged runtime must pass `--version` plus feedback-bridge smoke.

### Final release build

`scripts/release.ps1 -Version vX.Y.Z` additionally requires Inno Setup 6 and must place into `dist/`:

```text
MusicArk-X.Y.Z-win-x64.zip
MusicArk-Setup-X.Y.Z-x64.exe
SHA256SUMS.txt
update-manifest.json
```

---

## v0.11.x upload/recovery compatibility gate

Although the release-focus window starts at v0.12, v0.12–v0.15 build on production Yandex upload/recovery behavior introduced in v0.11.x. The full Python/Flutter suites therefore remain the mandatory compatibility gate for:

- single-track upload preflight and delivery-unknown behavior;
- no automatic retry after uncertain Stage 2 delivery;
- batch/recovery state;
- owned-playlist boundaries;
- explicit rights confirmation;
- Controlled Sync upload-only behavior;
- safe audit serialization.

Do not remove those tests merely because the release matrix is named v0.12–v0.15.

---

## Manual Windows acceptance before v1.0.0

Blocking manual checks are tracked separately in GitHub Issue #34:

- fresh-profile clean install;
- launch without system Python/source checkout;
- portable ZIP launch;
- reinstall same version;
- upgrade from previous accepted build;
- uninstall while preserving MusicArk user data;
- verify uninstall does not remove WARP;
- update endpoint unavailable;
- explicit confirmation before installer launch;
- feedback actions;
- RU/EN and Light/Dark/System;
- Yandex / Local / Matching / Missing / Downloads / Sync / Metadata Editor smoke.

For every item record exact commit/tag, artifact SHA-256 and `PASS`, `FAIL` or `NOT VERIFIED`.
