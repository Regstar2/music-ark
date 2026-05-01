"""Desktop platform bridge for Flutter UI <-> Python core communication.

This module keeps business logic in Python core modules and exposes
UI-safe JSON commands for the desktop client.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


def _configure_stdio_utf8() -> None:
    """Ensure JSON with non-ASCII (track titles, etc.) survives Windows pipe/console encodings."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        rc = getattr(stream, "reconfigure", None)
        if callable(rc):
            try:
                rc(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

from musicark.core.app import MusicArkApp
from musicark.core.config import AppConfig, load_config, save_config
from musicark.core.errors import StorageError
from musicark.matching.engine import MatchingEngine
from musicark.providers.local_library import LocalLibraryProvider
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository
from musicark.sync.planner import SyncPlanner


def _db_query(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        raise StorageError(f"Bridge query failed: {exc}") from exc


def build_snapshot(base_dir: Path | None = None) -> dict[str, Any]:
    """Return a UI-oriented snapshot without embedding business logic in Dart."""
    app = MusicArkApp(base_dir=base_dir)
    db_path = app.db_init()

    counts_row = _db_query(
        db_path,
        """
        SELECT
          (SELECT COUNT(*) FROM providers),
          (SELECT COUNT(*) FROM provider_tracks),
          (SELECT COUNT(*) FROM local_audio_files),
          (SELECT COUNT(*) FROM download_tasks),
          (SELECT COUNT(*) FROM match_conflicts WHERE status='open'),
          (SELECT COUNT(*) FROM sync_plans),
          (SELECT COUNT(*) FROM audit_log)
        """,
    )[0]

    providers = [
        {
            "provider_id": row[0],
            "display_name": row[1],
            "capabilities": json.loads(row[2] or "{}"),
            "metadata": json.loads(row[3] or "{}"),
            "updated_at": row[4],
        }
        for row in _db_query(
            db_path,
            """
            SELECT provider_id, display_name, capabilities_json, metadata_json, updated_at
            FROM providers
            ORDER BY provider_id
            """,
        )
    ]

    collection = [
        {
            "provider_id": row[0],
            "external_id": row[1],
            "title": row[2],
            "artists": row[3],
            "album": row[4],
            "updated_at": row[5],
        }
        for row in _db_query(
            db_path,
            """
            SELECT
              provider_id,
              external_id,
              json_extract(payload_json, '$.title') AS title,
              COALESCE(json_extract(payload_json, '$.artists[0]'), '') AS first_artist,
              COALESCE(json_extract(payload_json, '$.album_title'), '') AS album_title,
              updated_at
            FROM provider_tracks
            ORDER BY id DESC
            LIMIT 200
            """,
        )
    ]

    local_files = [
        {
            "id": row[0],
            "path": row[1],
            "duration_seconds": row[2],
            "codec": row[3],
            "updated_at": row[4],
        }
        for row in _db_query(
            db_path,
            """
            SELECT id, path, duration_seconds, codec, updated_at
            FROM local_audio_files
            ORDER BY updated_at DESC
            LIMIT 200
            """,
        )
    ]

    queue = [
        asdict(task) for task in DownloadStorageRepository(db_path).list_tasks()[-200:]
    ]

    conflicts = [
        {
            "id": row[0],
            "provider_id": row[1],
            "external_id": row[2],
            "local_file_id": row[3],
            "confidence": row[4],
            "reason": row[5],
            "created_at": row[6],
        }
        for row in _db_query(
            db_path,
            """
            SELECT id, source_provider_id, source_external_id, local_file_id, confidence, reason, created_at
            FROM match_conflicts
            WHERE status='open'
            ORDER BY confidence DESC, id DESC
            LIMIT 200
            """,
        )
    ]

    sync_plan_headers = _db_query(
        db_path,
        """
        SELECT id, created_at, dry_run, summary_json, status
        FROM sync_plans
        ORDER BY created_at DESC
        LIMIT 20
        """,
    )
    sync_plans = []
    sync_repo = SyncStorageRepository(db_path)
    for row in sync_plan_headers:
        operation_count = 0
        try:
            operation_count = len(sync_repo.get_plan(row[0]).operations)
        except StorageError:
            operation_count = 0
        sync_plans.append(
            {
                "id": row[0],
                "created_at": row[1],
                "dry_run": bool(row[2]),
                "summary": json.loads(row[3] or "{}"),
                "status": row[4],
                "operation_count": operation_count,
            }
        )

    logs = [
        {
            "id": row[0],
            "event_type": row[1],
            "entity_type": row[2],
            "entity_id": row[3],
            "status": row[4],
            "details": row[5],
            "created_at": row[6],
        }
        for row in _db_query(
            db_path,
            """
            SELECT id, event_type, entity_type, entity_id, status, details, created_at
            FROM audit_log
            ORDER BY id DESC
            LIMIT 200
            """,
        )
    ]

    config = load_config(base_dir)
    return {
        "database_path": str(db_path),
        "dashboard": {
            "providers": counts_row[0],
            "remote_tracks": counts_row[1],
            "local_files": counts_row[2],
            "download_tasks": counts_row[3],
            "open_conflicts": counts_row[4],
            "sync_plans": counts_row[5],
            "audit_events": counts_row[6],
        },
        "providers": providers,
        "collection": collection,
        "local_library": local_files,
        "download_queue": queue,
        "sync_plans": sync_plans,
        "conflicts": conflicts,
        "logs": logs,
        "settings": asdict(config),
    }


def run_action(name: str, base_dir: Path | None = None, path: str | None = None) -> dict[str, Any]:
    """Run state-changing action in Python core, returning JSON-safe result."""
    app = MusicArkApp(base_dir=base_dir)
    db_path = app.db_init()

    if name == "scan_yandex":
        return YandexMusicProvider(base_dir=base_dir).scan_all(database_path=db_path)
    if name == "scan_local":
        if not path:
            raise ValueError("scan_local action requires --path.")
        return LocalLibraryProvider().scan(Path(path), db_path)
    if name == "match_run":
        return MatchingEngine(db_path).run()
    if name == "sync_plan":
        plan = SyncPlanner(db_path).build_plan(dry_run=True)
        return {
            "id": plan.id,
            "created_at": plan.created_at,
            "dry_run": plan.dry_run,
            "summary": plan.summary,
            "operations_count": len(plan.operations),
        }
    raise ValueError(f"Unsupported action: {name}")


def update_settings(
    base_dir: Path | None = None,
    database_path: str | None = None,
    log_level: str | None = None,
) -> dict[str, Any]:
    """Update persisted app settings without touching core logic from UI."""
    config = load_config(base_dir)
    new_config = AppConfig(
        database_path=database_path or config.database_path,
        log_level=log_level or config.log_level,
    )
    saved_path = save_config(new_config, base_dir)
    return {"saved_to": str(saved_path), "settings": asdict(new_config)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-platform-bridge")
    parser.add_argument("--base-dir", default=None, help="Base directory for config and DB.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("snapshot", help="Return full UI snapshot JSON.")

    action_parser = subparsers.add_parser("action", help="Run one UI action.")
    action_parser.add_argument("--name", required=True, help="Action name.")
    action_parser.add_argument("--path", default=None, help="Optional path for scan_local.")

    settings_parser = subparsers.add_parser("settings-update", help="Update config values.")
    settings_parser.add_argument("--database-path", default=None)
    settings_parser.add_argument("--log-level", default=None)
    return parser


def main() -> int:
    _configure_stdio_utf8()
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        if args.command == "snapshot":
            print(json.dumps(build_snapshot(base_dir), ensure_ascii=False))
            return 0
        if args.command == "action":
            print(json.dumps(run_action(args.name, base_dir=base_dir, path=args.path), ensure_ascii=False))
            return 0
        if args.command == "settings-update":
            print(
                json.dumps(
                    update_settings(
                        base_dir=base_dir,
                        database_path=args.database_path,
                        log_level=args.log_level,
                    ),
                    ensure_ascii=False,
                )
            )
            return 0
        parser.print_help()
        return 1
    except Exception as exc:  # noqa: BLE001 - bridge must send explicit errors to UI.
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
