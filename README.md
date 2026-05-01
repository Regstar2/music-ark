# MusicArk

MusicArk is a cross-platform application for preserving and restoring a personal music collection.

This repository currently contains the `v0.11-restore-upload-experimental` stage (v0.9–v0.10 features included):

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
- experimental Yandex upload / restore scaffolding (feature flag — library **has no Client upload API** today; probes return `not_supported`);
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
  - `musicark yandex experimental-upload --confirm --local-file-id <id> --original-external-id <yandex_track_id>`
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
    musicark-bridge action --name experimental_yandex_upload --payload '{"confirm":true,"local_file_id":1,"original_external_id":"123456"}'
    ```

Configure `experimental_yandex_upload` in `.musicark/config.json` (Settings toggle in Flutter) or set env `MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD=1` to force-enable the flag when loading config.

Upload limitations today: MarshalX **`yandex-music` Python client exposes no upload API**, so probes end in `not_supported`. A dedicated “MusicArk restore” playlist is **not created automatically** until a documented API appears; the mapping helpers only prepare JSON for eventual `track_sources` linkage.

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

## Desktop UI (v0.11)

- **Metadata** tab (mutagen-backed tag edits + backups under `.musicark/metadata_backups`).
- **Settings → Experimental Yandex upload** toggle + guarded `experimental_yandex_upload` bridge probe (normally `not_supported`).

```bash
cd ui/musicark_ui
flutter pub get
flutter run -d windows
```
