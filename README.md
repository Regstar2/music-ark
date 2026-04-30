# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.5-download-system` stage:

- Python package skeleton;
- core configuration and error model;
- SQLite bootstrap and minimal audit log;
- provider architecture (registry, capabilities, track source);
- provider metadata persistence in SQLite;
- Yandex Music provider scan pipeline with normalized models and raw responses;
- local library recursive scan with local audio indexing;
- universal download-system with queue, task statuses and local import provider;
- CLI commands:
  - `musicark health-check`
  - `musicark db-init`
  - `musicark config-show`
  - `musicark yandex auth-check`
  - `musicark yandex scan-likes`
  - `musicark yandex scan-playlists`
  - `musicark yandex scan-all`
  - `musicark local scan --path "<music_folder>"`
  - `musicark local list`
  - `musicark local stats`
  - `musicark download task-create --task-type local_import --source-id "<file>" --provider-id local_import --target-folder ".musicark/imported"`
  - `musicark download queue`
  - `musicark download run --id "<task_id>"`
  - `musicark import file "<file>"`

Yandex dependency is pinned in `requirements-yandex.txt`:

```bash
pip install -r requirements-yandex.txt
```

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
musicark health-check
```
