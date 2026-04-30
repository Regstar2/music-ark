# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.3-yandex-scan` stage:

- Python package skeleton;
- core configuration and error model;
- SQLite bootstrap and minimal audit log;
- provider architecture (registry, capabilities, track source);
- provider metadata persistence in SQLite;
- Yandex Music provider scan pipeline with normalized models and raw responses;
- CLI commands:
  - `musicark health-check`
  - `musicark db-init`
  - `musicark config-show`
  - `musicark yandex auth-check`
  - `musicark yandex scan-likes`
  - `musicark yandex scan-playlists`
  - `musicark yandex scan-all`

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
