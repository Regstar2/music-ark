<div align="center">

# MusicArk

A Windows application for managing a local music collection and matching it against a Yandex Music library. It helps identify missing tracks, review recording variants, repair metadata, and perform controlled synchronization.

[![Platform](https://img.shields.io/badge/platform-Windows_x64-0A7EA4?style=for-the-badge)](#requirements)

[Русский](README.md) · **English**

[Quick start](#quick-start) ·
[Documentation](#documentation) ·
[Releases](../../releases) ·
[Feedback](#feedback)

</div>

---

## About

MusicArk is intended for users who want to keep a local copy of their music collection and compare it with their Yandex Music library. The application treats track identity, metadata, recording variant, and collection coverage as separate concepts: high title similarity alone is not considered a confirmed match.

Core workflow:

```text
Yandex Music = desired collection
        ↓
Local Library = actual files
        ↓
Identity Matching + Variant + Coverage
        ↓
Missing / Wanted
        ↓
Download / Metadata / confirmed Sync or Upload actions
```

## Project status

- stage: **Stable**;
- current release: **v1.0.0**;
- release platform: **Windows x64**;
- SQLite schema: **1.9.0**;
- Authenticode: **UNSIGNED**.

`v1.0.0` is published as the first stable release. The installer and executable are not Authenticode-signed, so Windows SmartScreen may display a warning on first launch.

## Features

- Yandex Music sign-in with a user-provided token;
- cache-first browsing of liked tracks, playlists, and liked albums;
- indexing of multiple local folders without modifying files during an ordinary Scan;
- Identity Matching between Yandex Music tracks and local files;
- Variant analysis and user `ORIGINAL / CENSORED` labels;
- Coverage / Missing workflows for absent or review-required tracks;
- Downloads queue with Wanted, retry, cancel, remove, and bulk actions;
- built-in playback for local and prepared Yandex tracks;
- Metadata Editor for safe MP3/ID3 writes, artwork, and confirmed Yandex identity binding;
- manual upload of owned or otherwise permitted MP3 files to Yandex Music and recovery workflows;
- Controlled Sync with an explicit plan and confirmation before apply;
- System / Direct / Custom proxy modes;
- RU/EN interface with System / Light / Dark themes;
- portable package, per-user installer, and a verifiable update mechanism.

For libraries containing several thousand tracks, MusicArk uses cache-first loading, bounded batches, persisted queues, and sequential workers for expensive operations.

## Quick start

1. Open the [latest GitHub Release](../../releases/latest).
2. Download `MusicArk-Setup-1.0.0-x64.exe` for a regular installation or `MusicArk-1.0.0-win-x64.zip` for portable use.
3. Start MusicArk.
4. If needed, sign in to Yandex Music with a user-provided token.
5. Add local-library folders and run Scan.
6. Use Matching, Coverage, and Downloads to review collection state.

The packaged Windows build does not require a separately installed Python interpreter or a cloned source checkout.

## Requirements

- 64-bit Windows;
- internet access for Yandex Music features, updates, and external providers;
- a Yandex Music user token for features that require authentication.

External service availability should not be required for local browsing and work with already cached data.

## Installation

### Installer

`MusicArk-Setup-1.0.0-x64.exe` installs the application for the current user under:

```text
%LOCALAPPDATA%\Programs\Music Ark
```

### Portable

`MusicArk-1.0.0-win-x64.zip` can be extracted to any user-writable directory and started through `Music Ark.exe`.

Mutable user data is stored separately under:

```text
%LOCALAPPDATA%\MusicArk
```

A normal uninstall is not intended to remove the database, caches, or user settings.

## Usage

Ordinary Scan, Matching, Variant, Coverage, and Sync-plan inspection do not modify user audio files.

An existing MP3 changes only after an explicit Metadata Editor action. Writes use a temporary copy, MPEG/metadata validation, and atomic replacement. Unknown and custom ID3 frames are preserved unless the user explicitly edits them.

Removing a failed/needs-review download task removes the queue record, not a completed audio file.

## Network and proxy

MusicArk supports three modes:

```text
System  — operating-system network settings
Direct  — direct connection
Custom  — user-provided proxy
```

Built-in Cloudflare WARP management has been removed from the release runtime. MusicArk does not install or uninstall WARP automatically.

Failures in external metadata/download providers should remain local to the affected function and must not block work with the local library and cached data.

## Security

- Scan, Matching, Variant, and Coverage are not intended to modify local audio files;
- MP3 writes happen only after an explicit user action;
- upload and sync require explicit selection or confirmation;
- the updater verifies installer size and SHA-256 before launch;
- release packages include `LICENSE`, `THIRD_PARTY_NOTICES.md`, and third-party license texts.

## Privacy

- tokens, cookies, signed media URLs, and proxy passwords must not be committed to Git;
- the Flutter UI does not receive the Yandex token or protected provider media URLs for playback/download;
- automatic feedback diagnostics are limited to MusicArk version, OS, and architecture and exclude the music library, local paths, and credentials;
- mutable installed state is stored in a per-user data directory instead of beside program files.

## Updating

The stable updater consumes `update-manifest.json` from the latest GitHub Release.

```text
check   → fetch and validate manifest
prepare → download installer and verify size + SHA-256
apply   → after confirmation, re-verify and launch installer
```

An unavailable update endpoint must not prevent normal MusicArk startup. Installing an update requires an explicit user confirmation.

## Development

Running from source requires Python, Flutter, and the Windows toolchain expected by the current project.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter run -d windows
```

## Build

Final Windows packaging runs from source state where `VERSION` already matches the release version:

```powershell
.\scripts\release.ps1 -Version v1.0.0
```

For `v1.0.0`, the pipeline produces:

```text
MusicArk-1.0.0-win-x64.zip
MusicArk-Setup-1.0.0-x64.exe
SHA256SUMS.txt
update-manifest.json
```

## Testing

The main local regression entry point is:

```powershell
.\scripts\ci.ps1
```

The repository also contains `Trusted CI` for trusted owner PR/workflow-dispatch runs on a self-hosted Windows x64 runner. External or otherwise untrusted fork PRs must not execute on the owner's persistent self-hosted runner.

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — project history;
- [v1.0.0 release notes](docs/releases/v1.0.0_EN.md) — details of the first stable release;
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — redistributed components, licenses, and source obligations.

## Feedback

Bugs and feature requests are accepted through [GitHub Issues](../../issues).

Do not publish tokens, cookies, proxy passwords, signed URLs, or other credentials in issue reports.

## Limitations

- Windows x64 is the only release platform;
- full safe metadata writing is implemented for MP3/ID3; other supported formats may remain read-only in Metadata Editor;
- some provider functionality depends on external APIs and service availability;
- automatic `ORIGINAL / CENSORED` analysis is not treated as absolute truth and uncertain cases require review;
- MusicArk is not a bidirectional filesystem mirror and must not automatically delete, rename, or overwrite existing local tracks;
- update/install actions do not proceed without an explicit user step;
- v1.0.0 is distributed without an Authenticode signature.

## License

MusicArk's own code is distributed under the [MIT License](LICENSE).

Third-party components keep their own licenses. Their notices and source obligations are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the [`licenses/`](licenses/) directory.

Yandex Music integration uses an unofficial API through the third-party `yandex-music` library. MusicArk is not an official Yandex product and is not affiliated with Yandex.
