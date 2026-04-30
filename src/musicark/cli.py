"""Minimal CLI entrypoint for MusicArk v0.1."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from musicark.core.app import MusicArkApp
from musicark.core.config import load_config
from musicark.core.logging_setup import setup_logging
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexMusicProvider,
    YandexTokenMissingError,
)
from musicark.providers.local_library import LocalLibraryError, LocalLibraryProvider
from musicark.download.provider import LocalImportProvider
from musicark.download.provider import YandexMusicDownloadProvider
from musicark.download.system import DownloadSystem
from musicark.matching.engine import MatchingEngine
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.sync.planner import SyncPlanner


def build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="musicark")
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Override base directory used for config and local DB.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health-check", help="Show basic core health state.")
    subparsers.add_parser("db-init", help="Initialize SQLite schema.")
    subparsers.add_parser("config-show", help="Print current configuration.")

    yandex_parser = subparsers.add_parser("yandex", help="Run Yandex provider commands.")
    yandex_subparsers = yandex_parser.add_subparsers(dest="yandex_command", required=True)
    yandex_subparsers.add_parser("auth-check", help="Validate Yandex token and account access.")
    yandex_subparsers.add_parser("scan-likes", help="Scan liked tracks only.")
    yandex_subparsers.add_parser("scan-playlists", help="Scan playlists only.")
    yandex_subparsers.add_parser("scan-all", help="Scan account, likes and playlists.")
    yandex_download_track = yandex_subparsers.add_parser(
        "download-track", help="Download one Yandex track by id."
    )
    yandex_download_track.add_argument("--id", required=True, help="Yandex track id.")
    yandex_download_track.add_argument(
        "--quality",
        default="best",
        help="Download quality hint: best or bitrate number (e.g. 192, 320).",
    )
    yandex_download_track.add_argument(
        "--target-folder",
        default=".musicark/downloads/yandex",
        help="Destination folder for downloaded track.",
    )
    yandex_download_likes = yandex_subparsers.add_parser(
        "download-likes", help="Download liked tracks through download-system."
    )
    yandex_download_likes.add_argument("--limit", type=int, default=10, help="Max tracks to enqueue.")
    yandex_download_likes.add_argument(
        "--quality",
        default="best",
        help="Download quality hint: best or bitrate number.",
    )
    yandex_download_likes.add_argument(
        "--target-folder",
        default=".musicark/downloads/yandex",
        help="Destination folder for downloaded tracks.",
    )

    local_parser = subparsers.add_parser("local", help="Run local library commands.")
    local_subparsers = local_parser.add_subparsers(dest="local_command", required=True)

    local_scan = local_subparsers.add_parser("scan", help="Scan local music folder.")
    local_scan.add_argument("--path", required=True, help="Absolute or relative path to scan.")

    local_subparsers.add_parser("list", help="List indexed local files.")
    local_subparsers.add_parser("stats", help="Show local library statistics.")

    download_parser = subparsers.add_parser("download", help="Manage download task queue.")
    download_subparsers = download_parser.add_subparsers(dest="download_command", required=True)

    download_create = download_subparsers.add_parser("task-create", help="Create download task.")
    download_create.add_argument("--task-type", required=True, help="Task type, e.g. local_import.")
    download_create.add_argument("--source-id", required=True, help="Source identifier or file path.")
    download_create.add_argument("--provider-id", required=True, help="Download provider id.")
    download_create.add_argument("--target-folder", required=True, help="Target folder path.")

    download_run = download_subparsers.add_parser("run", help="Run single task by id.")
    download_run.add_argument("--id", required=True, help="Download task id.")

    download_cancel = download_subparsers.add_parser("cancel", help="Cancel task by id.")
    download_cancel.add_argument("--id", required=True, help="Download task id.")

    download_retry = download_subparsers.add_parser("retry", help="Retry failed task by id.")
    download_retry.add_argument("--id", required=True, help="Download task id.")

    download_subparsers.add_parser("queue", help="Show download queue.")

    import_parser = subparsers.add_parser("import", help="Import commands via download-system.")
    import_subparsers = import_parser.add_subparsers(dest="import_command", required=True)
    import_file = import_subparsers.add_parser("file", help="Import single local file.")
    import_file.add_argument("path", help="Source file path to import.")
    import_file.add_argument(
        "--target-folder",
        default=".musicark/imported",
        help="Destination folder for imported file.",
    )

    match_parser = subparsers.add_parser("match", help="Run matching engine commands.")
    match_subparsers = match_parser.add_subparsers(dest="match_command", required=True)
    match_subparsers.add_parser("run", help="Run automatic matching pass.")
    match_subparsers.add_parser("list-conflicts", help="List unresolved matching conflicts.")
    match_accept = match_subparsers.add_parser("accept", help="Accept conflict manually.")
    match_accept.add_argument("--conflict-id", type=int, required=True, help="Conflict identifier.")

    sync_parser = subparsers.add_parser("sync", help="Sync planning commands.")
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command", required=True)
    sync_plan = sync_subparsers.add_parser("plan", help="Build sync plan.")
    sync_plan.add_argument("--dry-run", action="store_true", help="Build plan without execution (default).")
    sync_show = sync_subparsers.add_parser("plan-show", help="Show saved sync plan.")
    sync_show.add_argument("--id", required=True, help="Sync plan id.")
    sync_cancel = sync_subparsers.add_parser("plan-cancel", help="Cancel saved sync plan.")
    sync_cancel.add_argument("--id", required=True, help="Sync plan id.")
    return parser


def main() -> int:
    """Run MusicArk CLI command."""
    parser = build_parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None

    app = MusicArkApp(base_dir=base_dir)
    setup_logging(level=app.config.log_level)

    if args.command == "health-check":
        print(json.dumps(app.health_check(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "db-init":
        db_path = app.db_init()
        print(f"SQLite initialized: {db_path}")
        return 0

    if args.command == "config-show":
        config = load_config(base_dir)
        print(json.dumps(asdict(config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "yandex":
        provider = YandexMusicProvider(base_dir=base_dir)
        download_system = DownloadSystem(app.db_init())
        download_system.register_provider(LocalImportProvider())
        download_system.register_provider(YandexMusicDownloadProvider(base_dir=base_dir))
        try:
            if args.yandex_command == "auth-check":
                print(json.dumps(provider.auth_check(), ensure_ascii=False, indent=2))
                return 0
            if args.yandex_command == "scan-likes":
                print(
                    json.dumps(
                        [asdict(track) for track in provider.list_tracks()],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if args.yandex_command == "scan-playlists":
                print(
                    json.dumps(
                        [asdict(playlist) for playlist in provider.list_playlists()],
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            if args.yandex_command == "scan-all":
                db_path = app.db_init()
                result = provider.scan_all(database_path=db_path)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if args.yandex_command == "download-track":
                task = download_system.create_task(
                    task_type="yandex_download",
                    source_id=args.id,
                    provider_id="yandex_music_download",
                    target_folder=args.target_folder,
                )
                task.raw_payload = {"track_id": args.id, "quality": args.quality}
                # update payload before execution
                from musicark.storage.download_storage import DownloadStorageRepository

                DownloadStorageRepository(app.resolve_database_path()).upsert_task(task)
                result = download_system.run_task(task.id)
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
                return 0
            if args.yandex_command == "download-likes":
                tracks = provider.list_tracks()[: max(args.limit, 0)]
                results = []
                from musicark.storage.download_storage import DownloadStorageRepository

                task_storage = DownloadStorageRepository(app.resolve_database_path())
                for track in tracks:
                    task = download_system.create_task(
                        task_type="yandex_download",
                        source_id=track.external_id,
                        provider_id="yandex_music_download",
                        target_folder=args.target_folder,
                    )
                    task.raw_payload = {"track_id": track.external_id, "quality": args.quality}
                    task_storage.upsert_task(task)
                    done = download_system.run_task(task.id)
                    results.append(asdict(done))
                print(json.dumps(results, ensure_ascii=False, indent=2))
                return 0
        except (YandexTokenMissingError, YandexAuthenticationError, YandexMusicError) as exc:
            print(str(exc))
            return 2

    if args.command == "local":
        db_path = app.db_init()
        storage = LocalLibraryStorageRepository(db_path)
        provider = LocalLibraryProvider()
        try:
            if args.local_command == "scan":
                result = provider.scan(Path(args.path), db_path)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if args.local_command == "list":
                print(json.dumps(storage.list_local_audio_files(), ensure_ascii=False, indent=2))
                return 0
            if args.local_command == "stats":
                print(json.dumps(storage.local_stats(), ensure_ascii=False, indent=2))
                return 0
        except LocalLibraryError as exc:
            print(str(exc))
            return 2

    if args.command in {"download", "import"}:
        db_path = app.db_init()
        system = DownloadSystem(db_path)
        system.register_provider(LocalImportProvider())
        system.register_provider(YandexMusicDownloadProvider(base_dir=base_dir))

        if args.command == "download":
            if args.download_command == "task-create":
                task = system.create_task(
                    task_type=args.task_type,
                    source_id=args.source_id,
                    provider_id=args.provider_id,
                    target_folder=args.target_folder,
                )
                print(json.dumps(asdict(task), ensure_ascii=False, indent=2))
                return 0
            if args.download_command == "run":
                task = system.run_task(args.id)
                print(json.dumps(asdict(task), ensure_ascii=False, indent=2))
                return 0
            if args.download_command == "cancel":
                task = system.cancel_task(args.id)
                print(json.dumps(asdict(task), ensure_ascii=False, indent=2))
                return 0
            if args.download_command == "retry":
                task = system.retry_task(args.id)
                print(json.dumps(asdict(task), ensure_ascii=False, indent=2))
                return 0
            if args.download_command == "queue":
                queue = [asdict(task) for task in system.queue()]
                print(json.dumps(queue, ensure_ascii=False, indent=2))
                return 0

        if args.command == "import" and args.import_command == "file":
            task = system.create_task(
                task_type="local_import",
                source_id=args.path,
                provider_id="local_import",
                target_folder=args.target_folder,
            )
            task = system.run_task(task.id)
            print(json.dumps(asdict(task), ensure_ascii=False, indent=2))
            return 0

    if args.command == "match":
        db_path = app.db_init()
        engine = MatchingEngine(db_path)
        if args.match_command == "run":
            result = engine.run()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.match_command == "list-conflicts":
            conflicts = engine.list_conflicts()
            print(json.dumps(conflicts, ensure_ascii=False, indent=2))
            return 0
        if args.match_command == "accept":
            engine.accept(args.conflict_id)
            print(json.dumps({"status": "accepted", "conflict_id": args.conflict_id}, ensure_ascii=False, indent=2))
            return 0

    if args.command == "sync":
        db_path = app.db_init()
        planner = SyncPlanner(db_path)
        if args.sync_command == "plan":
            plan = planner.build_plan(dry_run=True if args.dry_run else True)
            print(
                json.dumps(
                    {
                        "id": plan.id,
                        "created_at": plan.created_at,
                        "dry_run": plan.dry_run,
                        "summary": plan.summary,
                        "operations_preview": [asdict(op) for op in plan.operations[:20]],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.sync_command == "plan-show":
            plan = planner.show_plan(args.id)
            print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
            return 0
        if args.sync_command == "plan-cancel":
            planner.cancel_plan(args.id)
            print(json.dumps({"status": "cancelled", "id": args.id}, ensure_ascii=False, indent=2))
            return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
