"""Direct-Python Stage1 probe for the recovered Yandex UGC upload contract.

Ground truth from the official desktop client and sanitized ASAR analysis resolves
Stage1 to ``POST /loader/upload-url`` with query values:

- ``uid`` = cached account uid;
- ``playlist-id`` = ``<uid>:<playlistKind>``;
- ``path`` = selected file name only.

This diagnostic intentionally reads no OAuth credential, sends no cookies, makes
exactly one Stage1 request, never follows ``post-target`` and never sends audio
bytes. Query/header values, signed URLs and response scalar values are not emitted.
Production upload capabilities remain disabled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

import httpx
import requests

import yandex_upload_cdp_oauth_probe as cdp_base
import yandex_upload_live_poc as live
from musicark.providers.yandex_upload_transport import (
    YandexUploadProtocolError,
    YandexUploadTransport,
    _safe_exception_kinds,
)


_FORMAT = "musicark-yandex-upload-python-composite-stage1-probe-v1"
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"
_STAGE1_PATH = "/loader/upload-url"
_TRANSPORTS = {"requests", "http2"}
_PROFILES = {"bare", "desktop"}


def _validate_base_url(value: str) -> str:
    clean = str(value or "").strip().rstrip("/")
    parsed = urlparse(clean)
    host = (parsed.hostname or "").lower().rstrip(".")
    yandex_host = any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in ("yandex.ru", "yandex.net", "yandex.com")
    )
    if (
        parsed.scheme != "https"
        or not host
        or not yandex_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise YandexUploadProtocolError(
            "Stage-one base URL must be an explicit HTTPS Yandex host/prefix without credentials, query, or fragment."
        )
    return clean


def _headers(profile: str) -> dict[str, str]:
    clean = str(profile or "").strip().lower()
    if clean not in _PROFILES:
        raise YandexUploadProtocolError("Unsupported Python Stage1 client profile.")
    headers = {"Accept": "application/json"}
    if clean == "desktop":
        headers["X-Yandex-Music-Client"] = _DESKTOP_CLIENT_LABEL
    return headers


def _cached_context(args: argparse.Namespace, base_dir: Path | None) -> cdp_base._CachedStage1Context:  # noqa: SLF001
    context_args = argparse.Namespace(
        file=args.file,
        playlist_kind=args.playlist_kind,
        playlist_id_source="kind",
    )
    return cdp_base._cached_stage1_context(context_args, base_dir)  # noqa: SLF001


def _post_once(
    endpoint: str,
    *,
    params: dict[str, str],
    headers: dict[str, str],
    transport: str,
    trust_env: bool,
    timeout: float,
) -> Any:
    clean_transport = str(transport or "").strip().lower()
    if clean_transport not in _TRANSPORTS:
        raise YandexUploadProtocolError("Unsupported Python Stage1 transport mode.")

    if clean_transport == "http2":
        with httpx.Client(
            http1=True,
            http2=True,
            trust_env=trust_env,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            return client.post(endpoint, params=dict(params), headers=dict(headers))

    kwargs = {
        "params": dict(params),
        "headers": dict(headers),
        "timeout": timeout,
        "allow_redirects": False,
    }
    if trust_env:
        return requests.post(endpoint, **kwargs)
    with requests.Session() as session:
        session.trust_env = False
        return session.post(endpoint, **kwargs)


def _decode_shape(response: Any) -> tuple[dict[str, Any], bool, bool, bool]:
    if not 200 <= int(response.status_code) <= 299:
        return {"type": "unavailable"}, False, False, False
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return {"type": "unavailable"}, False, False, False
    shape = YandexUploadTransport._shape(payload)  # noqa: SLF001 - existing sanitized shape helper.
    if not isinstance(payload, dict):
        return shape, False, False, False
    return (
        shape,
        isinstance(payload.get("post-target"), str) and bool(payload.get("post-target")),
        isinstance(payload.get("poll-result"), str) and bool(payload.get("poll-result")),
        isinstance(payload.get("ugc-track-id"), str) and bool(payload.get("ugc-track-id")),
    )


def _http_version(response: Any, transport: str) -> str | None:
    if str(transport).lower() == "http2":
        value = str(getattr(response, "http_version", "") or "").strip()
        return value or None
    raw = getattr(response, "raw", None)
    version = getattr(raw, "version", None)
    if version == 11:
        return "HTTP/1.1"
    if version == 10:
        return "HTTP/1.0"
    return None


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if not args.confirm_prepare:
        raise YandexUploadProtocolError("Direct Python Stage1 probe requires --confirm-prepare.")
    if not args.confirm_owned_file:
        raise YandexUploadProtocolError("Direct Python Stage1 probe requires --confirm-owned-file.")
    if args.timeout <= 0 or args.timeout > 120:
        raise YandexUploadProtocolError("--timeout must be between 0 and 120 seconds.")

    base_dir = Path(args.base_dir) if args.base_dir else None
    live._require_research_opt_in(base_dir)  # noqa: SLF001 - shared explicit research safety gate.
    context = _cached_context(args, base_dir)
    playlist_kind = str(args.playlist_kind or "").strip()
    if not playlist_kind:
        raise YandexUploadProtocolError("Playlist kind is empty.")

    base_url = _validate_base_url(args.stage1_base_url)
    endpoint = f"{base_url}{_STAGE1_PATH}"
    params = {
        "uid": context.uid,
        "playlist-id": f"{context.uid}:{playlist_kind}",
        "path": context.file_path.name,
    }
    headers = _headers(args.client_profile)
    trust_env = not bool(args.ignore_env)

    try:
        response = _post_once(
            endpoint,
            params=params,
            headers=headers,
            transport=args.transport,
            trust_env=trust_env,
            timeout=float(args.timeout),
        )
    except (requests.RequestException, httpx.HTTPError) as exc:
        payload = {
            "format": _FORMAT,
            "mode": "prepare",
            "status": "diagnostic_complete",
            "diagnosis": "python-network-path-failed",
            "network": {"stage1Sent": True, "stage2Sent": False, "pythonNetworkStack": True},
            "playlist": {
                "kind": playlist_kind,
                "playlistIdFormula": "uid:playlistKind",
                "playlistIdSourceUsed": "uid-colon-kind-static-ground-truth",
                "contextSource": "musicark-local-cache",
            },
            "file": {**live._file_summary(context.file_path), "stage1PathMode": "name"},  # noqa: SLF001
            "stage1": {
                "origin": base_url,
                "httpResponseReceived": False,
                "httpStatus": None,
                "httpVersion": None,
                "uploadUrlPresent": False,
                "pollUrlPresent": False,
                "trackIdPresent": False,
                "responseShape": {"type": "unavailable"},
                "authorizationSource": "none",
                "transport": str(args.transport),
                "clientProfile": str(args.client_profile),
                "trustEnv": trust_env,
                "transportFailureClasses": _safe_exception_kinds(exc),
            },
            "probe": {
                "mutation": "stage1-upload-slot-only",
                "automaticRetry": False,
                "requestCount": 1,
                "formulaEvidence": "official-desktop-runtime-and-asar-v46-v47",
            },
            "safety": _safety(args),
        }
        return payload, 3

    status = int(response.status_code)
    response_shape, post_target, poll_result, track_id = _decode_shape(response)
    slot = bool(200 <= status <= 299 and post_target)
    payload = {
        "format": _FORMAT,
        "mode": "prepare",
        "status": "upload_url_obtained" if slot else "diagnostic_complete",
        "diagnosis": "direct-python-stage1-confirmed" if slot else "python-http-response-without-upload-slot",
        "network": {"stage1Sent": True, "stage2Sent": False, "pythonNetworkStack": True},
        "playlist": {
            "kind": playlist_kind,
            "playlistIdFormula": "uid:playlistKind",
            "playlistIdSourceUsed": "uid-colon-kind-static-ground-truth",
            "contextSource": "musicark-local-cache",
        },
        "file": {**live._file_summary(context.file_path), "stage1PathMode": "name"},  # noqa: SLF001
        "stage1": {
            "origin": base_url,
            "httpResponseReceived": True,
            "httpStatus": status,
            "httpVersion": _http_version(response, args.transport),
            "uploadUrlPresent": post_target,
            "pollUrlPresent": poll_result,
            "trackIdPresent": track_id,
            "responseShape": response_shape,
            "authorizationSource": "none",
            "transport": str(args.transport),
            "clientProfile": str(args.client_profile),
            "trustEnv": trust_env,
        },
        "probe": {
            "mutation": "stage1-upload-slot-only",
            "automaticRetry": False,
            "requestCount": 1,
            "formulaEvidence": "official-desktop-runtime-and-asar-v46-v47",
        },
        "safety": _safety(args),
    }
    return payload, (0 if slot else 3)


def _safety(args: argparse.Namespace) -> dict[str, bool]:
    return {
        "credential_values_included": False,
        "credential_store_read": False,
        "authorization_header_sent": False,
        "authorization_values_included": False,
        "cookie_values_included": False,
        "cookies_sent": False,
        "header_values_included": False,
        "query_values_included": False,
        "uid_value_included": False,
        "playlist_composite_value_included": False,
        "path_value_included": False,
        "signed_urls_included": False,
        "raw_response_bodies_included": False,
        "audio_bytes_sent": False,
        "stage2_sent": False,
        "automatic_retry": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send exactly one direct-Python Stage1 request using the recovered uid:playlistKind + filename contract."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--stage1-base-url", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--playlist-kind", required=True)
    parser.add_argument("--transport", choices=("requests", "http2"), default="http2")
    parser.add_argument("--client-profile", choices=("bare", "desktop"), default="desktop")
    parser.add_argument("--ignore-env", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-prepare", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - sanitized CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
