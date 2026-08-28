# Windows Acceptance Evidence — v1.0.0 Release Freeze Historical RC

Issue: [#34](https://github.com/Regstar2/music-ark/issues/34)

This file records factual Windows distribution evidence for the first public
MusicArk release candidate before the final `v1.0.0` publication pass. `PASS`
means the check was actually executed against the recorded source/artifact. If
the environment that produced this historical evidence could not prove a manual
condition, the result stayed `NOT VERIFIED`.

Current publication gates for the final `v1.0.0` source/tag/artifacts are
tracked in `docs/release/release-checklist.md` and
[#35](https://github.com/Regstar2/music-ark/issues/35). Issue #34 was closed by
the owner on 2026-08-27 after the Windows distribution acceptance matrix had
been exercised against the release candidate. That owner acceptance does not
replace the final post-publication smoke of files downloaded from the published
GitHub Release.

## Source

| Field | Value |
|---|---|
| Branch | `release/v1.0-windows-acceptance` |
| Source SHA | `097926cb2ef4a11a6b900e3eaeef75f874656703` plus the local release-blocker fixes committed with this evidence update |
| Baseline | v0.15.0 merged; v1.0.0 feature freeze |
| Final v1.0.0 tag/release | NOT CREATED |

## Process State

| Check | Result | Evidence | Notes |
|---|---|---|---|
| Main synchronized before branching | PASS | `main` fast-forwarded to `09e91c01208d9a5f80750ee738511df5587296ec` | Local pre-existing generated UI changes were preserved in git stash entries. |
| Working tree clean before branch | PASS | `git status --short --branch` returned only `## main...origin/main` before branch creation | No direct changes were made on `main`. |
| Issue #34 read with comments | PASS | `gh issue view 34 --json ...` | No comments were present. |
| Issue #35 read with comments | PASS | `gh issue view 35 --json ...` | Read only as source of truth; #35 work is deferred until #34 result is known. |
| Issues linked to Project #2 | NOT VERIFIED | `gh project item-add` failed: token lacks `read:project` | Owner action required unless GitHub automation links the items. |

## Automated Release Gate

Command:

```powershell
.\scripts\ci.ps1
```

| Check | Result | Evidence | Notes |
|---|---|---|---|
| Commit SHA | PASS | Local gate executed on `097926cb2ef4a11a6b900e3eaeef75f874656703` plus the release-blocker working-tree fixes | Final pushed PR head SHA must be read from GitHub after push. |
| Selected Python version | PASS | `scripts/resolve-python.ps1` selected `3.13`; runtime `3.13.14` | `py -3.13` reported `3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)]`. |
| Version consistency | PASS | `MusicArk version declarations are consistent: 0.15.0` |  |
| Python tests | PASS | `Ran 617 tests in 30.483s` / `OK` | Full `unittest discover -s tests -p 'test_*.py' -v`. |
| v0.11.x upload/recovery compatibility | PASS | Covered by full Python/Flutter suites in `.\scripts\ci.ps1` | Live Yandex mutations intentionally removed from normal CI environment. |
| v0.12 regressions | PASS | Covered by full Python/Flutter suites in `.\scripts\ci.ps1` | Includes external metadata / WARP UI regression coverage. |
| v0.13 regressions | PASS | Covered by full Python suite in `.\scripts\ci.ps1` |  |
| v0.14 regressions | PASS | Performance smoke + full suites passed |  |
| v0.15 regressions | PASS | Packaging smoke + full suites passed |  |
| Flutter analyze | PASS | `flutter analyze --no-fatal-infos` exit code 0 | Analyzer still reports 36 non-fatal info diagnostics. |
| Flutter tests | PASS | `flutter test` ended `+155: All tests passed!` | Full suite, not focused-only. |
| Flutter Windows build | PASS | Historical evidence built `build\windows\x64\runner\Release\musicark_ui.exe`; current packaging contract expects `build\windows\x64\runner\Release\Music Ark.exe` and must be revalidated before release. |  |
| Performance report | PASS | `.musicark/performance/release-regression.json` generated | 1k/10k/50k deterministic evidence generated. |
| SQLite query audit | PASS | `.musicark/performance/sqlite-query-audit.json` generated |  |
| Portable package smoke | PASS | `tools/package_windows.ps1 -SkipInstaller -PythonVersion 3.13` and full `.\scripts\ci.ps1` passed | Packaging pip installs use `--no-cache-dir` to avoid dirty user-cache permission failures. |
| Live Yandex mutation in normal CI | N/A | `scripts/ci.ps1` removes live mutation env vars | Live mutation is intentionally outside ordinary CI. |

## Release Candidate Artifacts

These are release-candidate evidence artifacts only. They are not final v1.0.0 artifacts and must not be published as the stable release.

| Filename | Size | SHA-256 | Source SHA | Build environment |
|---|---:|---|---|---|
| `MusicArk-0.15.0-win-x64.zip` | 87540082 | `641cd698045f63deaf6cb0ae242a1d1c0368646800f4a0d804822d3a31333069` | local release-fix working tree based on `097926cb2ef4a11a6b900e3eaeef75f874656703` | Windows 11, Python 3.13.14, Flutter Windows release build |

## Manual Windows Acceptance Matrix

| Check | Result | Evidence | Notes |
|---|---|---|---|
| A. Clean install under a new/clean Windows user profile | NOT VERIFIED | Not run yet | Requires real installer execution in an isolated profile. |
| B. Installed launch without checkout, `.venv`, or system Python | NOT VERIFIED | Not run yet | Must be checked from installed app, outside source tree. |
| C. Portable ZIP launch outside repository | NOT VERIFIED | Not run yet | Must be checked from independent extraction directory. |
| D. Reinstall same version preserves user data | NOT VERIFIED | Not run yet | Requires representative `%LOCALAPPDATA%\MusicArk` state before reinstall. |
| E. Upgrade from previous accepted build preserves DB/config/keyring/user data | NOT VERIFIED | Not run yet | Requires an actual previous build. Do not infer from installer code. |
| F. Uninstall removes program files and preserves `%LOCALAPPDATA%\MusicArk` | NOT VERIFIED | Not run yet | Must also confirm external software such as WARP is not removed. |
| G. Unavailable/invalid update endpoint remains non-fatal | NOT VERIFIED | Not run yet | Settings must still open and show controlled update error. |
| H. Update check/prepare/apply confirmation contract | NOT VERIFIED | Not run yet | Installer must not launch without explicit confirmation. |
| I. Bug report and Feature request feedback actions | NOT VERIFIED | Not run yet | Must check browser open or copy-link fallback and sanitized diagnostics. |
| J. RU/EN, Light/Dark/System, normal/narrow smoke | NOT VERIFIED | Not run yet | Requires packaged UI smoke. |
| K. Packaged application pages open | NOT VERIFIED | Not run yet | Yandex, Local Library, Matching, Missing, Downloads, Sync, Metadata Editor, Settings, Help, About. |

## Security / Privacy Audit

| Check | Result | Evidence | Notes |
|---|---|---|---|
| Current tree secret/private-data audit | NOT VERIFIED | Not run yet | Must avoid printing discovered secret values. |
| Practical git history audit | NOT VERIFIED | Not run yet | If real secrets are found, mark release blocker and rotate credentials. |
| Artifact/log secret audit | NOT VERIFIED | Not run yet | Requires built RC artifacts/logs. |

## Release Blockers

These were historical blockers for the environment that produced this file.
They are not the current final-publication blocker list.

- Project #2 linkage was `NOT VERIFIED` here because the available GitHub token
  lacked project scopes.
- Manual Windows acceptance was later confirmed by the owner in issue #34 and
  #34 is closed.
- Final security/privacy, public visibility, tag, GitHub Release and
  post-publication smoke gates remain tracked in
  `docs/release/release-checklist.md` and issue #35.

## Owner Actions Required

- Use issue #35 for the remaining final-publication gates.
- Perform the owner GUI smoke of the published downloaded artifacts after the
  GitHub Release is available.
