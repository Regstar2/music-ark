"""Explicit one-track direct-Python PoC for the recovered Yandex UGC upload flow.

This tool is intentionally separate from production MusicArk capabilities. It uses
only the runtime/static-ground-truth Stage1 contract:

- ``uid`` = authenticated account uid;
- ``playlist-id`` = ``<uid>:<playlistKind>``;
- ``path`` = selected file name only;
- no Stage1 Authorization or cookies;
- Stage2 is exactly one multipart ``file`` POST to the dynamic Yandex target.

Before sending audio bytes it authenticates through MusicArk's existing Yandex
credential boundary only to verify the current account uid, target playlist and
pre-upload membership. The saved credential is not used for Stage1 or Stage2.
The dynamic target must be HTTPS on a Yandex domain. Production upload remains
disabled; this CLI requires two explicit research/live opt-ins and confirmation.

Stage1 and Stage2 transports are selected independently. ``--ignore-env`` applies
to both, so a transport differential never silently re-enables environment proxy
settings. There is no fallback and no automatic upload retry.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import requests

import yandex_upload_live_poc as live
import yandex_upload_python_composite_stage1_probe as stage1
from musicark.providers.yandex_upload_transport import (
    YandexUploadProtocolError,
    YandexUploadSlot,
    YandexUploadTransport,
    _safe_exception_kinds,
)


_FORMAT = "musicark-yandex-upload-python-composite-live-poc-v2"
_STAGE2_TRANSPORTS = {"requests", "http2"}


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _require_live_confirmation(args: argparse.Namespace, base_dir: Path | None) -> None:
    live._require_research_opt_in(base_dir)  # noqa: SLF001 - shared explicit research gate.
    if not _enabled(os.getenv("MUSICARK_YANDEX_UPLOAD_LIVE")):
        raise YandexUploadProtocolError(
            "Live mutation is disabled. Set MUSICARK_YANDEX_UPLOAD_LIVE=1 for this explicit local PoC."
        )
    if not args.confirm_owned_file:
        raise YandexUploadProtocolError("Direct Python upload PoC requires --confirm-owned-file.")
    if not args.confirm_upload:
        raise YandexUploadProtocolError("Direct Python upload PoC requires --confirm-upload.")


def _validate_dynamic_upload_target(value: str) -> str:
    clean = str(value or "").strip()
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
    ):
        raise YandexUploadProtocolError("Dynamic upload target is not an allowed HTTPS Yandex host.")
    return clean


def _authenticated_target(
    *,
    base_dir: Path | None,
    playlist_kind: str,
    expected_uid: str,
) -> tuple[Any, Any, set[str], str]:
    client = live._build_client(base_dir)  # noqa: SLF001 - existing credential boundary for read-back only.
    playlist = live._resolve_playlist(client, playlist_kind)  # noqa: SLF001
    uid_value = getattr(playlist, "uid", None) or getattr(client, "account_uid", None)
    authenticated_uid = str(uid_value or "").strip()
    if not authenticated_uid:
        raise YandexUploadProtocolError("Unable to resolve authenticated playlist owner uid.")
    if authenticated_uid != str(expected_uid):
        raise YandexUploadProtocolError(
            "Cached account uid does not match the authenticated target account; no upload request was sent."
        )
    before_ids = live._playlist_track_ids(playlist)  # noqa: SLF001
    return client, playlist, before_ids, authenticated_uid


def _stage1_slot(
    *,
    args: argparse.Namespace,
    uid: str,
    file_path: Path,
    playlist_kind: str,
) -> tuple[YandexUploadSlot, int, str | None]:
    base_url = stage1._validate_base_url(args.stage1_base_url)  # noqa: SLF001
    endpoint = f"{base_url}{stage1._STAGE1_PATH}"  # noqa: SLF001
    params = {
        "uid": uid,
        "playlist-id": f"{uid}:{playlist_kind}",
        "path": file_path.name,
    }
    headers = stage1._headers(args.client_profile)  # noqa: SLF001
    trust_env = not bool(args.ignore_env)
    try:
        response = stage1._post_once(  # noqa: SLF001
            endpoint,
            params=params,
            headers=headers,
            transport=args.transport,
            trust_env=trust_env,
            timeout=float(args.timeout),
        )
    except (requests.RequestException, httpx.HTTPError) as exc:
        raise YandexUploadProtocolError(
            f"Direct Python Stage1 failed (transport={_safe_exception_kinds(exc)})."
        ) from exc

    status = int(response.status_code)
    if not 200 <= status <= 299:
        raise YandexUploadProtocolError(f"Direct Python Stage1 returned HTTP {status}.")
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise YandexUploadProtocolError("Direct Python Stage1 returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise YandexUploadProtocolError("Direct Python Stage1 returned an unexpected response shape.")

    upload_url = _validate_dynamic_upload_target(YandexUploadTransport._extract_upload_url(payload))  # noqa: SLF001
    slot = YandexUploadSlot(
        upload_url=upload_url,
        response_shape=YandexUploadTransport._shape(payload),  # noqa: SLF001
        poll_url=YandexUploadTransport._extract_poll_url(payload),  # noqa: SLF001
        track_id=YandexUploadTransport._extract_track_id(payload),  # noqa: SLF001
    )
    return slot, status, stage1._http_version(response, args.transport)  # noqa: SLF001


def _stage2_post_once(
    slot: YandexUploadSlot,
    file_path: Path,
    *,
    transport: str,
    trust_env: bool,
    timeout: float,
) -> Any:
    """Send exactly one multipart Stage2 request with no auth, fallback or retry."""
    path = Path(file_path)
    if not path.is_file():
        raise YandexUploadProtocolError(f"Upload file does not exist: {path}")
    if path.stat().st_size <= 0:
        raise YandexUploadProtocolError("Refusing to upload an empty file.")

    clean_transport = str(transport or "").strip().lower()
    if clean_transport not in _STAGE2_TRANSPORTS:
        raise YandexUploadProtocolError("Unsupported Python Stage2 transport mode.")

    with path.open("rb") as stream:
        files = {"file": (path.name, stream)}
        if clean_transport == "http2":
            with httpx.Client(
                http1=True,
                http2=True,
                trust_env=trust_env,
                timeout=timeout,
                follow_redirects=False,
            ) as client:
                return client.post(slot.upload_url, files=files)

        kwargs = {
            "files": files,
            "timeout": timeout,
            "allow_redirects": False,
        }
        if trust_env:
            return requests.post(slot.upload_url, **kwargs)
        with requests.Session() as session:
            session.trust_env = False
            return session.post(slot.upload_url, **kwargs)


def _stage2_http_version(response: Any, transport: str) -> str | None:
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


def _decode_stage2(response: Any) -> tuple[dict[str, Any], str | None]:
    payload: Any = None
    content_type = str(response.headers.get("Content-Type", "")).lower()
    if "json" in content_type:
        try:
            payload = response.json()
        except (TypeError, ValueError):
            payload = None
    return (
        YandexUploadTransport._shape(payload),  # noqa: SLF001 - sanitized response shape only.
        YandexUploadTransport._extract_track_id(payload),  # noqa: SLF001
    )


def _stage2_failure_payload(
    *,
    args: argparse.Namespace,
    context: Any,
    playlist_kind: str,
    slot: YandexUploadSlot,
    stage1_status: int,
    stage1_http_version: str | None,
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "format": _FORMAT,
        "mode": "upload",
        "status": "stage2_network_failed",
        "network": {
            "stage1Sent": True,
            "stage2Sent": True,
            "readBackSent": False,
            "pythonNetworkStack": True,
        },
        "playlist": {
            "kind": playlist_kind,
            "playlistIdFormula": "uid:playlistKind",
            "playlistIdSourceUsed": "uid-colon-kind-static-ground-truth",
            "authenticatedUidMatch": True,
        },
        "file": {**live._file_summary(context.file_path), "stage1PathMode": "name"},  # noqa: SLF001
        "stage1": {
            "origin": stage1._validate_base_url(args.stage1_base_url),  # noqa: SLF001
            "httpStatus": stage1_status,
            "httpVersion": stage1_http_version,
            "uploadUrlPresent": bool(slot.upload_url),
            "pollUrlPresent": bool(slot.poll_url),
            "trackIdPresent": bool(slot.track_id),
            "responseShape": slot.response_shape,
            "authorizationSource": "none",
            "transport": str(args.transport),
            "clientProfile": str(args.client_profile),
            "trustEnv": not bool(args.ignore_env),
        },
        "stage2": {
            "httpResponseReceived": False,
            "httpStatus": None,
            "httpVersion": None,
            "multipartField": "file",
            "targetHostValidated": True,
            "transport": str(args.stage2_transport),
            "trustEnv": not bool(args.ignore_env),
            "transportFailureClasses": _safe_exception_kinds(exc),
        },
        "probe": {
            "stage1RequestCount": 1,
            "stage2RequestCount": 1,
            "automaticUploadRetry": False,
            "automaticTransportFallback": False,
            "differentialVariable": "stage2-python-http-stack-and-shared-trust-env",
        },
        "safety": {
            "credential_values_included": False,
            "credential_store_read_for_authenticated_preflight": True,
            "stage1_authorization_header_sent": False,
            "stage2_authorization_header_sent": False,
            "cookie_values_included": False,
            "query_values_included": False,
            "uid_value_included": False,
            "playlist_composite_value_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "audio_submission_attempted": True,
            "audio_delivery_confirmed": False,
            "automatic_upload_retry": False,
            "automatic_transport_fallback": False,
        },
    }


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    base_dir = Path(args.base_dir) if args.base_dir else None
    _require_live_confirmation(args, base_dir)
    if args.readback_attempts < 1 or args.readback_attempts > 60:
        raise YandexUploadProtocolError("--readback-attempts must be between 1 and 60.")
    if args.readback_delay < 0 or args.readback_delay > 10:
        raise YandexUploadProtocolError("--readback-delay must be between 0 and 10 seconds.")
    if args.transfer_timeout <= 0 or args.transfer_timeout > 600:
        raise YandexUploadProtocolError("--transfer-timeout must be between 0 and 600 seconds.")

    context = stage1._cached_context(args, base_dir)  # noqa: SLF001
    file_path = context.file_path
    playlist_kind = str(args.playlist_kind or "").strip()
    if not playlist_kind:
        raise YandexUploadProtocolError("Playlist kind is empty.")

    client, playlist, before_ids, authenticated_uid = _authenticated_target(
        base_dir=base_dir,
        playlist_kind=playlist_kind,
        expected_uid=context.uid,
    )

    slot, stage1_status, stage1_http_version = _stage1_slot(
        args=args,
        uid=authenticated_uid,
        file_path=file_path,
        playlist_kind=playlist_kind,
    )

    try:
        stage2_response = _stage2_post_once(
            slot,
            file_path,
            transport=args.stage2_transport,
            trust_env=not bool(args.ignore_env),
            timeout=float(args.transfer_timeout),
        )
    except (requests.RequestException, httpx.HTTPError) as exc:
        return (
            _stage2_failure_payload(
                args=args,
                context=context,
                playlist_kind=playlist_kind,
                slot=slot,
                stage1_status=stage1_status,
                stage1_http_version=stage1_http_version,
                exc=exc,
            ),
            3,
        )

    stage2_status = int(stage2_response.status_code)
    stage2_shape, stage2_track_id = _decode_stage2(stage2_response)
    if not 200 <= stage2_status <= 299:
        payload = _stage2_failure_payload(
            args=args,
            context=context,
            playlist_kind=playlist_kind,
            slot=slot,
            stage1_status=stage1_status,
            stage1_http_version=stage1_http_version,
            exc=YandexUploadProtocolError("Stage2 returned a non-success HTTP status."),
        )
        payload["status"] = "stage2_http_failed"
        payload["stage2"].update(
            {
                "httpResponseReceived": True,
                "httpStatus": stage2_status,
                "httpVersion": _stage2_http_version(stage2_response, args.stage2_transport),
                "responseShape": stage2_shape,
                "transportFailureClasses": [],
            }
        )
        payload["safety"]["audio_delivery_confirmed"] = True
        return payload, 3

    reported_track_id = stage2_track_id or slot.track_id

    attempts_used = 0
    readback = live._classify_readback_identity(before_ids, before_ids, reported_track_id)  # noqa: SLF001
    for attempt in range(1, args.readback_attempts + 1):
        attempts_used = attempt
        current = live._refresh_playlist(client, playlist_kind, authenticated_uid)  # noqa: SLF001
        current_ids = live._playlist_track_ids(current)  # noqa: SLF001
        readback = live._classify_readback_identity(before_ids, current_ids, reported_track_id)  # noqa: SLF001
        if readback["verified"] or readback["ambiguous"]:
            break
        if attempt < args.readback_attempts:
            time.sleep(args.readback_delay)

    verified = bool(readback["verified"])
    payload = {
        "format": _FORMAT,
        "mode": "upload",
        "status": "verified" if verified else "uploaded_unverified",
        "network": {
            "stage1Sent": True,
            "stage2Sent": True,
            "readBackSent": True,
            "pythonNetworkStack": True,
        },
        "playlist": {
            "kind": playlist_kind,
            "playlistIdFormula": "uid:playlistKind",
            "playlistIdSourceUsed": "uid-colon-kind-static-ground-truth",
            "authenticatedUidMatch": True,
        },
        "file": {**live._file_summary(file_path), "stage1PathMode": "name"},  # noqa: SLF001
        "stage1": {
            "origin": stage1._validate_base_url(args.stage1_base_url),  # noqa: SLF001
            "httpStatus": stage1_status,
            "httpVersion": stage1_http_version,
            "uploadUrlPresent": bool(slot.upload_url),
            "pollUrlPresent": bool(slot.poll_url),
            "trackIdPresent": bool(slot.track_id),
            "responseShape": slot.response_shape,
            "authorizationSource": "none",
            "transport": str(args.transport),
            "clientProfile": str(args.client_profile),
            "trustEnv": not bool(args.ignore_env),
        },
        "stage2": {
            "httpResponseReceived": True,
            "httpStatus": stage2_status,
            "httpVersion": _stage2_http_version(stage2_response, args.stage2_transport),
            "responseShape": stage2_shape,
            "trackIdPresent": stage2_track_id is not None,
            "multipartField": "file",
            "targetHostValidated": True,
            "transport": str(args.stage2_transport),
            "trustEnv": not bool(args.ignore_env),
        },
        "readBack": {**readback, "attemptsUsed": attempts_used},
        "probe": {
            "stage1RequestCount": 1,
            "stage2RequestCount": 1,
            "automaticUploadRetry": False,
            "automaticTransportFallback": False,
            "formulaEvidence": "official-desktop-runtime-and-asar-v46-v47",
        },
        "safety": {
            "credential_values_included": False,
            "credential_store_read_for_authenticated_readback": True,
            "stage1_authorization_header_sent": False,
            "stage2_authorization_header_sent": False,
            "cookie_values_included": False,
            "query_values_included": False,
            "uid_value_included": False,
            "playlist_composite_value_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "audio_submission_attempted": True,
            "audio_delivery_confirmed": True,
            "automatic_upload_retry": False,
            "automatic_transport_fallback": False,
        },
    }
    return payload, (0 if verified else 3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload exactly one owned local track with the recovered direct-Python uid:kind contract."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--stage1-base-url", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--playlist-kind", required=True)
    parser.add_argument("--transport", choices=("requests", "http2"), default="http2")
    parser.add_argument("--stage2-transport", choices=("requests", "http2"), default="http2")
    parser.add_argument("--client-profile", choices=("bare", "desktop"), default="desktop")
    parser.add_argument("--ignore-env", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--transfer-timeout", type=float, default=120.0)
    parser.add_argument("--readback-attempts", type=int, default=15)
    parser.add_argument("--readback-delay", type=float, default=2.0)
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-upload", action="store_true")
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
