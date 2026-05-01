# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.10-metadata-editor` stage (desktop UI from v0.9 included):

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
- sync-planner with dry-run plans and persisted sync operations;
- Flutter Windows desktop UI with a Python `platform-bridge`;
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
  - `musicark sync plan --dry-run`
  - `musicark sync plan-show --id "<plan_id>"`
  - `musicark sync plan-cancel --id "<plan_id>"`
  - `musicark-bridge snapshot`
  - `musicark-bridge action --name sync_plan`
  - metadata (Flutter tab **Metadata**, or CLI):
    ```bash
    musicark-bridge action --name metadata_get --payload '{"local_file_id": 1}'
    musicark-bridge action --name metadata_update --payload '{"local_file_id":1,"confirm":true,"title":"T","artist":"A","album":"B","genre":"Rock"}'
    musicark-bridge action --name metadata_bulk_update --payload '{"local_file_ids":[1,2],"confirm":true,"genre":"Electronic"}'
    ```

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

## Desktop UI (v0.10)

Adds a **Metadata** tab for viewing/editing tags on indexed local files (mutagen-backed). Saves create a duplicate under `.musicark/metadata_backups` and audit log entries (`metadata_update`, `metadata_bulk_update`).

```bash
cd ui/musicark_ui
flutter pub get
flutter run -d windows
```
