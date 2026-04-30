# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.7-matching` stage:

- Python package skeleton;
- core configuration and error model;
- SQLite bootstrap and minimal audit log;
- provider architecture (registry, capabilities, track source);
- provider metadata persistence in SQLite;
- Yandex Music provider scan pipeline with normalized models and raw responses;
- local library recursive scan with local audio indexing;
- universal download-system with queue, task statuses and local import provider;
- yandex download provider integrated into download-system (single and batch tasks);
- matching-engine with canonical tracks, links and conflict queue;
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
  - `musicark yandex download-track --id "<track_id>" --quality best`
  - `musicark yandex download-likes --limit 10 --quality best`
  - `musicark match run`
  - `musicark match list-conflicts`
  - `musicark match accept --conflict-id <id>`

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
