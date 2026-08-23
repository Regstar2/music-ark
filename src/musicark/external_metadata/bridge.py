"""JSON process bridge for external metadata and explicit proxy networking."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from musicark.core.config import load_config
from musicark.metadata.service import MetadataEditorService
from musicark.storage.database import initialize_database

from .automatic_resolver import AutomaticExternalMetadataResolver
from .credentials import ExternalCredentialStore
from .editor import ExternalMetadataEditor
from .network import ExternalNetworkTransport, NetworkSettingsStore


_COMMANDS = (
    "external_metadata_identify",
    "external_metadata_search",
    "external_metadata_compare",
    "external_metadata_apply",
    "network_settings_get",
    "network_settings_update",
    "network_test",
    "external_credentials_get",
    "external_credentials_update",
)


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return json.loads(raw)


def _database(base_dir: Path | None) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    if raw.is_absolute():
        return raw
    return (base_dir if base_dir is not None else Path.home()) / raw


def _error(exc: Exception) -> dict[str, Any]:
    return {"error": {"code": "external_metadata_error", "message": str(exc)}}


def _safe_network_error_detail(exc: Exception) -> str:
    text = str(exc).strip().replace("\r", " ").replace("\n", " ")
    text = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@\s]+)@", r"\1***@", text)
    text = re.sub(
        r"(?i)\b(token|api[_-]?key|password|secret|client)=([^&\s]+)",
        r"\1=***",
        text,
    )
    return text[:180]


def _network_probe(
    transport: ExternalNetworkTransport,
    source: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    optional: bool = False,
) -> dict[str, Any]:
    try:
        response = transport.get(
            url,
            params=params,
            headers={"User-Agent": "MusicArk/1.0"},
        )
        status = int(response.status_code)
        if 200 <= status < 400:
            state = "ok"
        elif status < 500:
            state = "host_reached"
        else:
            state = "failed"
        return {
            "source": source,
            "state": state,
            "optional": optional,
            "reachable": status < 500,
            "statusCode": status,
            "route": response.extensions.get("musicark_route"),
        }
    except Exception as exc:  # noqa: BLE001 - diagnostics isolate each provider.
        return {
            "source": source,
            "state": "failed",
            "optional": optional,
            "reachable": False,
            "error": type(exc).__name__,
            "errorDetail": _safe_network_error_detail(exc),
        }


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
    try:
        if args.command == "network_settings_get":
            payload = {"settings": settings.public()}
        elif args.command == "network_settings_update":
            body = _json_env("MUSICARK_EXTERNAL_PAYLOAD", {})
            if not isinstance(body, dict):
                raise ValueError("Network settings payload must be an object.")
            settings.save(body)
            payload = {"settings": settings.public()}
        elif args.command == "external_credentials_get":
            payload = {"credentials": ExternalCredentialStore().public_status()}
        elif args.command == "external_credentials_update":
            body = _json_env("MUSICARK_EXTERNAL_PAYLOAD", {})
            if not isinstance(body, dict):
                raise ValueError("Credential payload must be an object.")
            store = ExternalCredentialStore()
            for name, value in body.items():
                store.set(str(name), str(value or ""))
            payload = {
                "updated": sorted(str(name) for name in body),
                "credentials": store.public_status(),
            }
        elif args.command == "network_test":
            credentials = ExternalCredentialStore()
            transport = ExternalNetworkTransport(settings)
            items: list[dict[str, Any]] = []

            # Diagnostics exercise only currently supported release routes.
            # Optional metadata provider credentials are not exposed in Settings.
            acoustid_key = credentials.get("acoustid_key")
            if acoustid_key:
                items.append(
                    _network_probe(
                        transport,
                        "acoustid",
                        "https://api.acoustid.org/v2/lookup",
                        params={
                            "client": acoustid_key,
                            "trackid": "9ff43b6a-4f16-427c-93c2-92307ca505e0",
                            "meta": "recordings releasegroups compress",
                            "format": "json",
                        },
                        optional=True,
                    )
                )

            items.append(
                _network_probe(
                    transport,
                    "cover_art_archive",
                    "https://coverartarchive.org/",
                )
            )

            payload = {
                "items": items,
                "settings": settings.public(),
            }
        else:
            if args.local_file_id is None:
                raise ValueError("--local-file-id is required.")
            resolver = AutomaticExternalMetadataResolver(database_path, base_dir)
            editor = ExternalMetadataEditor(
                MetadataEditorService(
                    base_dir=base_dir,
                    database_path=database_path,
                ),
                resolver,
            )
            if args.command == "external_metadata_identify":
                payload = resolver.identify(
                    args.local_file_id,
                    continue_search=args.continue_search,
                )
            elif args.command == "external_metadata_search":
                payload = resolver.search(
                    args.local_file_id,
                    title=args.title,
                    artist=args.artist,
                    album=args.album,
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
                    args.local_file_id,
                    args.candidate_id,
                    [str(x) for x in selected],
                    confirm=bool(
                        isinstance(body, dict) and body.get("confirm") is True
                    ),
                )
    except Exception as exc:  # noqa: BLE001 - public JSON boundary.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
