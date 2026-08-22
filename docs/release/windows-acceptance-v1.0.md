# Windows Acceptance Evidence — v1.0.0 Release Freeze

Issue: [#34](https://github.com/Regstar2/music-ark/issues/34)

This file records factual Windows distribution evidence for the first public MusicArk release candidate. `PASS` means the check was actually executed against the recorded source/artifact. If the current environment cannot prove a manual condition, the result stays `NOT VERIFIED`.

## Source

| Field | Value |
|---|---|
| Branch | `release/v1.0-windows-acceptance` |
| Source SHA | `09e91c01208d9a5f80750ee738511df5587296ec` |
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
| Commit SHA | NOT VERIFIED | Not run yet | Must be recorded after CI execution. |
| Selected Python version | NOT VERIFIED | Not run yet | Must come from `scripts/resolve-python.ps1`. |
| Version consistency | NOT VERIFIED | Not run yet |  |
| Python tests | NOT VERIFIED | Not run yet |  |
| v0.11.x upload/recovery compatibility | NOT VERIFIED | Not run yet | Covered by full Python/Flutter suites. |
| v0.12 regressions | NOT VERIFIED | Not run yet |  |
| v0.13 regressions | NOT VERIFIED | Not run yet |  |
| v0.14 regressions | NOT VERIFIED | Not run yet |  |
| v0.15 regressions | NOT VERIFIED | Not run yet |  |
| Flutter analyze | NOT VERIFIED | Not run yet |  |
| Flutter tests | NOT VERIFIED | Not run yet |  |
| Flutter Windows build | NOT VERIFIED | Not run yet |  |
| Performance report | NOT VERIFIED | Not run yet | Expected at `.musicark/performance/release-regression.json`. |
| SQLite query audit | NOT VERIFIED | Not run yet | Expected at `.musicark/performance/sqlite-query-audit.json`. |
| Portable package smoke | NOT VERIFIED | Not run yet | Expected under `artifacts/v0.15.0/`. |
| Live Yandex mutation in normal CI | N/A | `scripts/ci.ps1` removes live mutation env vars | Live mutation is intentionally outside ordinary CI. |

## Release Candidate Artifacts

These are release-candidate evidence artifacts only. They are not final v1.0.0 artifacts and must not be published as the stable release.

| Filename | Size | SHA-256 | Source SHA | Build environment |
|---|---:|---|---|---|
| NOT VERIFIED |  |  |  | RC artifacts not built yet. |

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

- Project #2 linkage is `NOT VERIFIED` because the available GitHub token lacks project scopes.
- All automated, artifact, manual and security checks remain `NOT VERIFIED` until executed and recorded.

## Owner Actions Required

- Confirm or repair Project #2 linkage for Issues #34 and #35 if GitHub automation has not added them.
- Perform any manual Windows checks that cannot be executed in the current Codex environment; use the matrix above and record exact evidence.
