"""JSON process bridge for v0.12 external metadata and resilient networking."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from musicark.core.config import load_config
from musicark.metadata.service import MetadataEditorService
from musicark.storage.database import initialize_database

from .credentials import ExternalCredentialStore
from .editor import ExternalMetadataEditor
from .network import ExternalNetworkTransport, NetworkSettingsStore
from .resolver import ExternalMetadataResolver
from .warp import WarpService


_COMMANDS = (
    "external_metadata_identify",
    "external_metadata_search",
    "external_metadata_compare",
    "external_metadata_apply",
    "network_settings_get",
    "network_settings_update",
    "network_test",
    "external_credentials_update",
    "warp_status",
    "warp_install",
    "warp_enable",
    "warp_disable",
)


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    value = json.loads(raw)
    return value


def _database(base_dir: Path | None) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    if raw.is_absolute():
        return raw
    return (base_dir if base_dir is not None else Path.home()) / raw


def _error(exc: Exception) -> dict[str, Any]:
    return {"error": {"code": "external_metadata_error", "message": str(exc)}}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-external-metadata-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("command", choices=_COMMANDS)
    parser.add_argument("--local-file-id", type=int)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--artist", default="")
    parser.add_argument("--album", default="")
    parser.add_argument("--continue-search", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    database_path = _database(base_dir)
    initialize_database(database_path)
    settings = NetworkSettingsStore(base_dir)
    warp = WarpService(database_path)
    try:
        if args.command == "network_settings_get":
            payload = {"settings": settings.public()}
        elif args.command == "network_settings_update":
            body = _json_env("MUSICARK_EXTERNAL_PAYLOAD", {})
            if not isinstance(body, dict):
                raise ValueError("Network settings payload must be an object.")
            settings.save(body)
            payload = {"settings": settings.public()}
        elif args.command == "external_credentials_update":
            body = _json_env("MUSICARK_EXTERNAL_PAYLOAD", {})
            if not isinstance(body, dict):
                raise ValueError("Credential payload must be an object.")
            store = ExternalCredentialStore()
            for name, value in body.items():
                store.set(str(name), str(value or ""))
            payload = {"updated": sorted(str(name) for name in body)}
        elif args.command == "warp_status":
            payload = {"warp": warp.status().as_dict()}
        elif args.command == "warp_install":
            payload = {"warp": warp.install().as_dict()}
        elif args.command == "warp_enable":
            payload = {"warp": warp.connect().as_dict()}
        elif args.command == "warp_disable":
            payload = {"warp": warp.disconnect().as_dict()}
        elif args.command == "network_test":
            transport = ExternalNetworkTransport(settings)
            probes = {
                "musicbrainz": "https://musicbrainz.org/ws/2/recording?query=recording%3Atest&limit=1&fmt=json",
                "acoustid": "https://api.acoustid.org/",
                "cover_art_archive": "https://coverartarchive.org/",
                "discogs": "https://api.discogs.com/",
                "theaudiodb": "https://www.theaudiodb.com/",
                "lastfm": "https://ws.audioscrobbler.com/2.0/",
            }
            items = []
            for source, url in probes.items():
                try:
                    response = transport.get(url, headers={"User-Agent": "MusicArk/0.12.0"})
                    items.append({"source": source, "reachable": response.status_code < 500, "statusCode": response.status_code})
                except Exception as exc:  # noqa: BLE001
                    items.append({"source": source, "reachable": False, "error": type(exc).__name__})
            payload = {"items": items, "warp": warp.status().as_dict()}
        else:
            if args.local_file_id is None:
                raise ValueError("--local-file-id is required.")
            resolver = ExternalMetadataResolver(database_path, base_dir)
            editor = ExternalMetadataEditor(MetadataEditorService(base_dir=base_dir, database_path=database_path), resolver)
            if args.command == "external_metadata_identify":
                payload = resolver.identify(args.local_file_id, continue_search=args.continue_search)
            elif args.command == "external_metadata_search":
                payload = resolver.search(
                    args.local_file_id, title=args.title, artist=args.artist, album=args.album,
                    continue_search=args.continue_search,
                )
            elif args.command == "external_metadata_compare":
                payload = editor.compare(args.local_file_id, args.candidate_id)
            else:
                body = _json_env("MUSICARK_EXTERNAL_PAYLOAD", {})
                selected = body.get("selectedFields") if isinstance(body, dict) else []
                if not isinstance(selected, list):
                    raise ValueError("selectedFields must be an array.")
                payload = editor.apply(
                    args.local_file_id, args.candidate_id, [str(x) for x in selected],
                    confirm=bool(isinstance(body, dict) and body.get("confirm") is True),
                )
    except Exception as exc:  # noqa: BLE001 - public JSON boundary.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
