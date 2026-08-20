"""JSON process bridge for v0.12 external metadata and resilient networking."""

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

from .credentials import ExternalCredentialStore
from .editor import ExternalMetadataEditor
from .network import ExternalNetworkTransport, NetworkMode, NetworkSettingsStore
from .resolver import ExternalMetadataResolver
from .warp import WarpService, WarpState


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


def _safe_network_error_detail(exc: Exception) -> str:
    """Return useful diagnostics without exposing proxy/API credentials."""
    text = str(exc).strip().replace("\r", " ").replace("\n", " ")
    text = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^/@\s]+)@", r"\1***@", text)
    text = re.sub(r"(?i)\b(token|api[_-]?key|password|secret)=([^&\s]+)", r"\1=***", text)
    return text[:180]


def _network_probe(
    transport: ExternalNetworkTransport,
    source: str,
    url: str,
    *,
    optional: bool = False,
) -> dict[str, Any]:
    try:
        response = transport.get(url, headers={"User-Agent": "MusicArk/0.12.0"})
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
        }
    except Exception as exc:  # noqa: BLE001 - diagnostics must isolate each provider.
        return {
            "source": source,
            "state": "failed",
            "optional": optional,
            "reachable": False,
            "error": type(exc).__name__,
            "errorDetail": _safe_network_error_detail(exc),
        }


def _not_configured(source: str) -> dict[str, Any]:
    return {
        "source": source,
        "state": "not_configured",
        "optional": True,
        "reachable": None,
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
            current_settings = settings.load()
            warp_status = warp.status()
            credentials = ExternalCredentialStore()
            items: list[dict[str, Any]] = []
            if current_settings.mode is NetworkMode.WARP and warp_status.state is not WarpState.PROXY_READY:
                items = [
                    {
                        "source": source,
                        "state": "failed",
                        "optional": False,
                        "reachable": False,
                        "error": "warp_local_proxy_not_ready",
                    }
                    for source in ("musicbrainz", "cover_art_archive")
                ]
            else:
                transport = ExternalNetworkTransport(settings)

                # MusicBrainz is the primary catalog. The ListenBrainz mapper is
                # tested only if the primary endpoint fails; it is a fallback,
                # not another mandatory dependency that should make a healthy
                # configuration look broken.
                musicbrainz = _network_probe(
                    transport,
                    "musicbrainz",
                    "https://musicbrainz.org/ws/2/recording?query=recording%3Atest&limit=1&fmt=json",
                )
                items.append(musicbrainz)
                if musicbrainz.get("state") != "ok":
                    items.append(_network_probe(
                        transport,
                        "listenbrainz_mapper",
                        "https://mapper.listenbrainz.org/mapping/lookup?artist_credit_name=Portishead&recording_name=Glory%20Box",
                        optional=True,
                    ))

                items.append(_network_probe(
                    transport,
                    "cover_art_archive",
                    "https://coverartarchive.org/",
                ))

                # These providers require credentials for actual lookups. Do not
                # report their unauthenticated 403/404 landing responses as API
                # health. A missing credential is a configuration state, not a
                # network error.
                credential_probes = (
                    ("acoustid", "acoustid_key", "https://api.acoustid.org/"),
                    ("discogs", "discogs_token", "https://api.discogs.com/"),
                    ("theaudiodb", "theaudiodb_key", "https://www.theaudiodb.com/"),
                    ("lastfm", "lastfm_key", "https://ws.audioscrobbler.com/2.0/"),
                )
                for source, credential_name, url in credential_probes:
                    if credentials.get(credential_name):
                        items.append(_network_probe(transport, source, url, optional=True))
                    else:
                        items.append(_not_configured(source))

            payload = {
                "items": items,
                "warp": warp_status.as_dict(),
                "settings": settings.public(),
            }
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
