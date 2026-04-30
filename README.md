# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.1-core-foundation` stage:

- Python package skeleton;
- core configuration and error model;
- SQLite bootstrap and minimal audit log;
- CLI commands:
  - `musicark health-check`
  - `musicark db-init`
  - `musicark config-show`

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
musicark health-check
```
