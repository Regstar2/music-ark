# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.2-provider-architecture` stage:

- Python package skeleton;
- core configuration and error model;
- SQLite bootstrap and minimal audit log;
- provider architecture (registry, capabilities, track source);
- provider metadata persistence in SQLite;
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
