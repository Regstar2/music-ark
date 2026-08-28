# MusicArk

[Русский](README.md) · **English**

**Code version: 1.0.0**  
**SQLite schema: 1.9.0**  
**Platform: Windows x64**

MusicArk is a Windows desktop application for managing a local music collection and matching it against a Yandex Music library. Its main purpose is collection integrity: identify tracks that are missing locally, surface recordings that need review, repair metadata, and perform only explicitly confirmed recovery actions.

> `v1.0.0` is the release-freeze version for the first public release. Source may contain final release fixes before the tag and GitHub Release exist; seeing `1.0.0` in source does not by itself mean the release has been published.

## What MusicArk does

- Yandex Music sign-in with a user-provided token without storing that token in the repository;
- cache-first browsing of liked tracks, playlists and explicitly liked albums;
- indexing of multiple local folders without modifying source audio during ordinary Scan;
- Identity Matching between Yandex Music tracks and local files;
- separate Variant analysis plus user `ORIGINAL / CENSORED` labels;
- Coverage / Missing workflows for absent or review-required tracks;
- Downloads queue with Wanted, retry/cancel/remove and bulk actions;
- built-in playback for local and prepared Yandex tracks;
- Metadata Editor for safe MP3/ID3 writes, artwork and user-confirmed Yandex identity binding;
- manual upload/recovery workflows for MP3 files the user is allowed to upload;
- Controlled Sync with an explicit plan and confirmation before apply;
- System / Direct / Custom proxy network modes;
- RU/EN UI with System/Light/Dark themes;
- portable Windows package, per-user Inno Setup installer, SHA-256 checksums and a verified update manifest.

## Product loop

```text
Yandex Library = desired collection
        ↓
Local Library = actual local files
        ↓
Identity Matching + Variant + Coverage
        ↓
Missing / Wanted
        ↓
Download / Metadata / confirmed Sync or Upload actions
```

MusicArk intentionally keeps **identity**, **metadata**, **variant**, and **coverage** separate. High title similarity alone never becomes a confirmed identity.

## Local-library safety

Normal Scan, Matching, Variant, Coverage and Sync-plan inspection do not modify user audio files.

An existing MP3 changes only after an explicit Metadata Editor action. Writes use a temporary copy in the same directory, MPEG/metadata validation and atomic replacement. Unknown/custom ID3 frames are preserved unless the user explicitly edits them.

Removing a failed/needs-review download task removes the queue record, not the completed audio file.

## Formats

Local-library reads use format adapters. Full safe metadata writing is implemented for **MP3/ID3**; other supported formats remain read-only in Metadata Editor unless a dedicated safe writer path exists.

Yandex upload uses only explicitly selected files and requires rights confirmation. The user is responsible for having the right to upload and use the content.

## Large libraries

The release candidate received a dedicated stabilization pass for collections containing several thousand tracks:

- Local Library opens cache-first and does not start recursive scanning during normal navigation;
- pages and bulk actions use bounded chunks;
- Matching persists batches through the active connection instead of opening a second SQLite writer in the hot loop;
- Select All / bulk decisions show processed/total progress;
- Downloads refreshes Wanted/queue state on initial load and page reactivation;
- Download All creates a visible persisted queue first, then drains it through a sequential worker;
- the Yandex download worker reuses one service/client session and has bounded retry/circuit-breaker behavior for systemic failures;
- repeated Yandex playback checks cache before expensive provider preparation.

## Network modes

MusicArk supports:

```text
System  — operating-system network settings
Direct  — direct connection
Custom  — user-provided proxy
```

Built-in Cloudflare WARP management has been removed from the release runtime. MusicArk does not install or uninstall WARP automatically.

Failures in external metadata/download providers should degrade locally and must not prevent work with already cached/local library data.

## Windows distribution

The final release pipeline produces:

```text
MusicArk-1.0.0-win-x64.zip
MusicArk-Setup-1.0.0-x64.exe
SHA256SUMS.txt
update-manifest.json
```

Portable and installed builds include the Flutter desktop app and frozen MusicArk backend runtime. Users do not need a separately installed Python interpreter or developer checkout.

The per-user installer defaults to `%LOCALAPPDATA%\Programs\Music Ark`. Mutable user data is kept separately under `%LOCALAPPDATA%\MusicArk` and is not intended to be removed by ordinary uninstall.

### Updates

The stable updater uses:

```text
https://github.com/Regstar2/music-ark/releases/latest/download/update-manifest.json
```

`MUSICARK_UPDATE_MANIFEST_URL` can override the endpoint for testing/deployment.

The update flow is deliberately separated:

```text
check   → fetch and validate manifest only
prepare → download installer and verify exact size + SHA-256
apply   → after explicit confirmation, re-verify and launch installer
```

An unavailable update endpoint must not prevent normal MusicArk startup.

## Data and privacy

- tokens, cookies, signed media URLs and proxy passwords must not be committed to Git;
- Flutter does not receive the Yandex token or protected provider media URLs for playback/download;
- automatic feedback diagnostics are limited to MusicArk version, OS and architecture and exclude the music library, local paths and credentials;
- installed mutable state lives in a per-user data directory rather than beside program files.

## v1.0.0 limitations

- Windows x64 is the only release platform;
- full metadata writing is MP3/ID3-only;
- some provider functionality depends on external APIs and service availability;
- automatic `ORIGINAL / CENSORED` analysis is not treated as absolute truth; uncertain cases require review;
- MusicArk is not a bidirectional filesystem mirror and must not automatically delete/rename existing local tracks;
- update/install actions do not proceed without an explicit user step;
- v1.0.0 is published as `UNSIGNED`: no suitable Authenticode code-signing certificate with a private key was found in the checked environment.

## License and third-party components

MusicArk's own code is distributed under the MIT License:

- [LICENSE](LICENSE)

Third-party components keep their own licenses. Windows artifacts include
Flutter, the CPython/PyInstaller runtime, Python packages, Dart packages,
FFmpeg, libmpv and other runtime libraries. Their notices/source obligations
are documented here:

- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- [licenses/](licenses/)

Yandex Music integration uses an unofficial API through the third-party
`yandex-music` library. MusicArk is not an official Yandex product and is not
affiliated with Yandex.

## Windows development run

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt

.\scripts\ci.ps1

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter run -d windows
```

Final Windows packaging:

```powershell
.\scripts\release.ps1 -Version v1.0.0
```

It must be run only from source where canonical `VERSION` is already `1.0.0`.

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — project history;
- [docs/releases/v1.0.0_EN.md](docs/releases/v1.0.0_EN.md) — public release notes;
- [docs/versions/v1.0.0.md](docs/versions/v1.0.0.md) — first-public-release boundary;
- [docs/release/release-checklist.md](docs/release/release-checklist.md) — final release gate;
- [docs/testing/release-regression-matrix.md](docs/testing/release-regression-matrix.md) — regression mapping;
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — third-party components and licenses;
- [GitHub Issues](https://github.com/Regstar2/music-ark/issues) — bugs and feature requests.

## Public release gate

Before stable `v1.0.0` publication, the project must still have evidence for final CI/tag/artifacts, public feedback/update reachability, legal files included in the final ZIP/installer, and factual installer-signing state (`UNSIGNED` for the currently checked environment). These gates are not satisfied merely because the release code exists in `main`.
