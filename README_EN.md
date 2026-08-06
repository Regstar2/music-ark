<div align="center">

# MusicArk

A desktop project for preserving and restoring a personal music collection. Its Python core indexes local files and provider data, stores state in SQLite, plans synchronization, and exposes both a CLI and a Flutter interface for Windows.

[Русский](README.md) · **English**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/UI-Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![SQLite](https://img.shields.io/badge/storage-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/status-desktop%20MVP-6F42C1?style=for-the-badge)

[Quick start](#quick-start) ·
[Commands](#commands) ·
[Architecture](#architecture) ·
[Limitations](#limitations)

</div>

---

## About

MusicArk builds a local catalog of a music collection and links records from different sources. The project combines a Python package, SQLite storage, a Yandex Music provider, a download queue, a matching engine, a sync planner, a JSON bridge, and a Flutter application.

Its primary safety rule is to build and persist a plan before executing explicitly approved operations. The current safe executor handles a limited set of download tasks and does not turn experimental restore code into automatic writes to a remote service.

## Project status

| Area | Status |
|---|---|
| Python core and CLI | Implemented |
| SQLite schema and forward migrations | Implemented |
| Local library scan | Implemented |
| Yandex Music data reading | Implemented through a separate dependency |
| Yandex Music track downloading | Implemented |
| Matching and sync planning | Implemented |
| Safe sync execution | Limited to `CREATE_DOWNLOAD_TASK` operations for Yandex downloads |
| Flutter Windows UI | Desktop MVP |
| Uploading tracks back to Yandex Music | Unsupported by the current client library |

## Features

- SQLite initialization and forward schema migrations;
- operation audit log;
- Yandex Music likes and playlist scanning;
- recursive local audio-file scanning;
- file, hash, and basic metadata indexing;
- provider-independent download queue with task states;
- single and batch Yandex Music downloads;
- matching engine with canonical tracks, links, and a conflict queue;
- persisted dry-run synchronization plans;
- guarded execution of supported operations from a saved plan;
- Mutagen-based metadata editing with local backups;
- `musicark` CLI, `musicark-bridge` JSON bridge, and Flutter dashboard.

## Quick start

Create an environment and install the Python package:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install -r requirements-yandex.txt
```

Initialize the database and check the CLI:

```powershell
musicark db-init
musicark health-check
```

Run unit tests:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Flutter UI:

```powershell
cd ui\musicark_ui
flutter pub get
flutter run -d windows
```

## Requirements

- Python 3.10 or newer;
- Windows for the current Flutter desktop client;
- Flutter/Dart for the UI;
- Yandex Music access and valid authentication for provider commands;
- local storage for SQLite, downloaded tracks, and metadata backups.

## Usage

### Local collection

```powershell
musicark local scan --path "D:\Music"
musicark local stats
musicark local list
```

### Yandex Music

```powershell
musicark yandex auth-check
musicark yandex scan-likes
musicark yandex scan-playlists
musicark yandex download-track --id "<track_id>" --quality best
```

### Matching and synchronization

```powershell
musicark match run
musicark match list-conflicts
musicark sync plan --dry-run
musicark sync execute-safe --confirm
```

Review the persisted plan before running safe synchronization. The command executes only supported operation types and requires explicit `--confirm`.

## Configuration

The main configuration is stored locally in `.musicark/config.json`. SQLite data, downloaded files, and metadata backups also remain in the local project workspace.

The experimental Yandex upload flag can be enabled in Flutter settings or with `MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD=1`, but it only enables a guarded probe. The current library exposes no upload API, so the normal result is `not_supported`.

Do not store provider tokens in tracked Git files.

## Commands

| Group | Examples |
|---|---|
| Status | `musicark health-check`, `musicark config-show` |
| Database | `musicark db-init` |
| Yandex Music | `musicark yandex auth-check`, `scan-likes`, `scan-playlists`, `download-track` |
| Local collection | `musicark local scan`, `local list`, `local stats` |
| Downloads | `musicark download queue`, `download run` |
| Matching | `musicark match run`, `match list-conflicts`, `match accept` |
| Synchronization | `musicark sync plan --dry-run`, `plan-show`, `plan-cancel`, `execute-safe --confirm` |
| Bridge | `musicark-bridge snapshot`, `musicark-bridge action --name <action>` |

Use the current CLI's `--help` output for the complete argument set.

## Architecture

```text
Flutter Windows UI
        │ JSON subprocess bridge
        ▼
musicark-bridge
        │
        ▼
Python application services
├── providers
├── local library
├── download queue
├── matching engine
├── sync planner / safe executor
├── metadata editor
└── audit log
        │
        ▼
SQLite + local music files
```

Provider-specific DTOs and APIs are isolated from the core model. Dangerous actions require explicit confirmation, and planning is separated from execution.

## Privacy

- the collection catalog and internal state are stored in local SQLite;
- local files are processed on the device;
- Yandex Music requests are made only when the corresponding provider is used;
- backups of edited tags are stored under `.musicark/metadata_backups`;
- the project has no separate MusicArk cloud backend.

A Yandex Music token provides account access and must be treated as a secret.

## Build

Install the Python package in editable mode:

```powershell
pip install -e .
```

Run the Flutter client from source:

```powershell
cd ui\musicark_ui
flutter pub get
flutter run -d windows
```

## Testing

Local command:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

The `.github/workflows/tests.yml` GitHub Actions workflow uses Python 3.12, installs the package with `pip install -e .`, and runs the unittest suite. Tests were not executed as part of this README-only change, so this document does not claim a result for the current branch.

## Documentation

| Task | Resource |
|---|---|
| Python package metadata | [pyproject.toml](pyproject.toml) |
| Core source code | [src/musicark/](src/musicark/) |
| Unit tests | [tests/](tests/) |
| Flutter client | [ui/musicark_ui/](ui/musicark_ui/) |
| CI | [.github/workflows/tests.yml](.github/workflows/tests.yml) |
| Yandex Music dependency | [requirements-yandex.txt](requirements-yandex.txt) |

## Limitations

- the current Yandex Music Python client does not expose an API for uploading tracks back to the library;
- `sync execute-safe` handles only a restricted type of approved download operation;
- the Flutter client targets Windows and has not been verified on other desktop platforms;
- automatic restore-playlist creation is not implemented;
- Python package version `0.1.0`, Flutter version `1.0.0+1`, and the v1.0 milestone are not synchronized;
- the project manages a personal collection and requires backups before bulk tag edits or plan execution;
- source-code distribution terms have not been defined.

## License

The repository has no root `LICENSE` file. Until a license is selected, the code must not be treated as open for copying, modification, or redistribution. Dependencies and external services retain their own terms.
