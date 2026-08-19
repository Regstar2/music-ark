"""Probe Yandex upload stage one through the official desktop Chromium network stack.

This diagnostic intentionally separates the remaining transport/auth hypotheses
after direct Python HTTP clients observed a remote protocol close before any HTTP
status. The request is initiated by MusicArk through a localhost-only CDP session,
but Chromium/Electron performs the network operation.

The probe uses only the OAuth credential already stored by MusicArk and sends it
with ``credentials: 'omit'`` so browser cookies/session state are not attached.
It performs stage one only: no dynamic upload target is followed and no audio
bytes are sent. Raw CDP messages, OAuth values, query values, response bodies and
signed URLs are never written to disk or returned in the sanitized result.

Unlike the direct Python PoC, this isolation probe deliberately does not
initialize the ``yandex-music`` Python client before the browser request. The uid
and playlist context are recovered from MusicArk's local SQLite cache so a
Python/Yandex transport failure cannot prevent the Chromium experiment itself.

Renderer ``fetch()`` failures are correlated with CDP ``Network.*`` events. This
is important because Chromium exposes CORS and renderer-policy failures as a
JavaScript ``TypeError`` even when the underlying network stack observed a
preflight or HTTP response. Only request method, status, safe CDP policy enums and
response structure are retained; request IDs and raw values are discarded.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import yandex_upload_cdp_probe as cdp
import yandex_upload_ground_truth_poc as groundtruth
import yandex_upload_live_poc as live
import yandex_upload_runtime_trace as runtime_trace
from musicark.core.config import load_config
from musicark.providers.yandex_upload_transport import (
    YandexOAuthStage1Requester,
    YandexUploadProtocolError,
)


_FORMAT = "musicark-yandex-upload-cdp-oauth-probe-v1"
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"
_PROVIDER_ID = "yandex_music"
_STAGE1_PATH = "/loader/upload-url"


@dataclass(frozen=True, slots=True)
class _CachedStage1Context:
    file_path: Path
    uid: str
    playlist_id: str
    playlist_id_source: str
    playlist_id_fallback: bool
    observed_visibility: str | None


@dataclass(slots=True)
class _Stage1NetworkObservation:
    post_request_observed: bool = False
    preflight_request_observed: bool = False
    post_http_status: int | None = None
    preflight_http_status: int | None = None
    post_loading_failed: bool = False
    preflight_loading_failed: bool = False
    blocked_reason: str | None = None
    cors_error: str | None = None
    response_shape: dict[str, Any] | None = None
    post_target_present: bool = False
    poll_result_present: bool = False
    ugc_track_id_present: bool = False


def _runtime_value(result: dict[str, Any]) -> dict[str, Any]:
    remote = result.get("result") if isinstance(result.get("result"), dict) else {}
    value = remote.get("value")
    if not isinstance(value, dict):
        raise YandexUploadProtocolError("Chromium OAuth probe returned no sanitized value.")
    return value


def _safe_shape(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"type": "unavailable"}
    shape_type = str(value.get("type") or "unavailable")
    if shape_type != "object":
        return {"type": shape_type[:40]}
    keys = value.get("keys") if isinstance(value.get("keys"), dict) else {}
    safe_keys: dict[str, dict[str, str]] = {}
    for key, descriptor in keys.items():
        if not isinstance(descriptor, dict):
            continue
        safe_keys[str(key)[:120]] = {"type": str(descriptor.get("type") or "unknown")[:40]}
    return {"type": "object", "keys": safe_keys}


def _safe_policy_label(value: Any) -> str | None:
    """Keep only stable CDP enum-like labels, never arbitrary error text."""
    clean = str(value or "").strip()
    if not clean or len(clean) > 120:
        return None
    if not all(character.isalnum() or character in {"-", "_"} for character in clean):
        return None
    return clean


def _resolve_database_path(base_dir: Path | None) -> Path:
    config = load_config(base_dir)
    raw = Path(config.database_path)
    if raw.is_absolute():
        return raw
    root = base_dir if base_dir is not None else Path.home()
    return root / raw


def _json_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _playlist_uuid_from_payload(payload: dict[str, Any]) -> str | None:
    raw_data = payload.get("raw_data")
    if not isinstance(raw_data, dict):
        raw_data = payload.get("rawData")
    if not isinstance(raw_data, dict):
        raw_data = {}
    for source in (raw_data, payload):
        for key in ("playlist_uuid", "playlistUuid", "uuid"):
            value = source.get(key)
            clean = str(value or "").strip()
            if clean:
                return clean
    return None


def _cached_stage1_context(args: argparse.Namespace, base_dir: Path | None) -> _CachedStage1Context:
    """Resolve stage-one context without any Yandex network call."""
    file_path = Path(args.file).expanduser().resolve()
    if not file_path.is_file():
        raise YandexUploadProtocolError("Selected upload file does not exist.")
    if file_path.stat().st_size <= 0:
        raise YandexUploadProtocolError("Selected upload file is empty.")

    playlist_kind = str(args.playlist_kind or "").strip()
    if not playlist_kind:
        raise YandexUploadProtocolError("Playlist kind is empty.")

    database_path = _resolve_database_path(base_dir)
    if not database_path.is_file():
        raise YandexUploadProtocolError(
            "MusicArk local cache is unavailable; Chromium OAuth probe will not fall back to the Python Yandex client."
        )

    account: dict[str, Any] = {}
    playlist_payload: dict[str, Any] = {}
    playlist_metadata: dict[str, Any] = {}
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            account_row = conn.execute(
                """
                SELECT account_json
                FROM provider_collection_snapshots
                WHERE provider_id=? AND collection_id='liked'
                LIMIT 1
                """,
                (_PROVIDER_ID,),
            ).fetchone()
            if account_row:
                account = _json_object(account_row[0])

            try:
                playlist_row = conn.execute(
                    """
                    SELECT payload_json
                    FROM provider_playlists
                    WHERE provider_id=? AND external_id=?
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (_PROVIDER_ID, playlist_kind),
                ).fetchone()
            except sqlite3.OperationalError:
                playlist_row = None
            if playlist_row:
                playlist_payload = _json_object(playlist_row[0])

            try:
                metadata_row = conn.execute(
                    """
                    SELECT metadata_json
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND collection_id=?
                    LIMIT 1
                    """,
                    (_PROVIDER_ID, f"playlist:{playlist_kind}"),
                ).fetchone()
            except sqlite3.OperationalError:
                metadata_row = None
            if metadata_row:
                playlist_metadata = _json_object(metadata_row[0])
    except sqlite3.Error as exc:
        raise YandexUploadProtocolError(
            f"Failed to read MusicArk local cache for Chromium OAuth probe ({type(exc).__name__})."
        ) from exc

    uid = ""
    for key in ("providerUserId", "provider_user_id", "uid"):
        clean = str(account.get(key) or "").strip()
        if clean:
            uid = clean
            break
    if not uid:
        raise YandexUploadProtocolError(
            "MusicArk cached account uid is unavailable; Chromium OAuth probe will not initialize the Python Yandex client."
        )

    requested_source = str(args.playlist_id_source or "uuid").strip().lower()
    playlist_id_fallback = False
    if requested_source == "uuid":
        cached_uuid = _playlist_uuid_from_payload(playlist_payload)
        if cached_uuid:
            playlist_id = cached_uuid
            actual_source = "uuid-cache"
        else:
            # Any HTTP response is already useful for this isolation experiment.
            # A kind fallback may yield 4xx, but still distinguishes network path
            # behavior from a renderer-policy failure.
            playlist_id = playlist_kind
            actual_source = "kind-diagnostic-fallback"
            playlist_id_fallback = True
    else:
        playlist_id = playlist_kind
        actual_source = "kind"

    visibility_value = playlist_metadata.get("visibility")
    if visibility_value is None:
        visibility_value = playlist_payload.get("visibility")
    observed_visibility = str(visibility_value).strip() if visibility_value else None

    return _CachedStage1Context(
        file_path=file_path,
        uid=uid,
        playlist_id=playlist_id,
        playlist_id_source=actual_source,
        playlist_id_fallback=playlist_id_fallback,
        observed_visibility=observed_visibility,
    )


def _expression(*, endpoint: str, oauth_token: str) -> str:
    """Build a one-shot browser fetch that returns structure, never secret values."""
    endpoint_literal = json.dumps(endpoint, ensure_ascii=False)
    token_literal = json.dumps(oauth_token, ensure_ascii=False)
    client_literal = json.dumps(_DESKTOP_CLIENT_LABEL)
    return f"""
(async () => {{
  const endpoint = {endpoint_literal};
  const oauth = {token_literal};
  try {{
    const response = await fetch(endpoint, {{
      method: 'POST',
      headers: {{
        'Accept': 'application/json',
        'Authorization': 'OAuth ' + oauth,
        'X-Yandex-Music-Client': {client_literal}
      }},
      credentials: 'omit',
      redirect: 'manual',
      cache: 'no-store'
    }});

    let responseShape = {{type: 'unavailable'}};
    let postTargetPresent = false;
    let pollResultPresent = false;
    let ugcTrackIdPresent = false;

    if (response.ok) {{
      try {{
        const payload = await response.json();
        if (payload && typeof payload === 'object' && !Array.isArray(payload)) {{
          const keys = Object.keys(payload).sort();
          const shapeKeys = {{}};
          for (const key of keys) {{
            const item = payload[key];
            shapeKeys[key] = {{
              type: Array.isArray(item) ? 'array' : (item === null ? 'null' : typeof item)
            }};
          }}
          responseShape = {{type: 'object', keys: shapeKeys}};
          postTargetPresent = typeof payload['post-target'] === 'string' && payload['post-target'].length > 0;
          pollResultPresent = typeof payload['poll-result'] === 'string' && payload['poll-result'].length > 0;
          ugcTrackIdPresent = typeof payload['ugc-track-id'] === 'string' && payload['ugc-track-id'].length > 0;
        }}
      }} catch (_) {{
        responseShape = {{type: 'unavailable'}};
      }}
    }}

    return {{
      networkCompleted: true,
      httpStatus: Number(response.status || 0),
      responseShape,
      postTargetPresent,
      pollResultPresent,
      ugcTrackIdPresent
    }};
  }} catch (error) {{
    return {{
      networkCompleted: false,
      errorName: error && error.name ? String(error.name) : 'Error'
    }};
  }}
}})()
""".strip()


def _is_stage1_url(value: Any, *, expected_origin: str) -> bool:
    try:
        actual = urlsplit(str(value or ""))
        expected = urlsplit(expected_origin)
    except ValueError:
        return False
    return bool(
        actual.scheme == expected.scheme
        and actual.hostname == expected.hostname
        and (actual.path or "/") == _STAGE1_PATH
    )


def _decode_stage1_body(result: dict[str, Any]) -> tuple[dict[str, Any], bool, bool, bool]:
    body = str(result.get("body") or "")
    base64_encoded = bool(result.get("base64Encoded"))
    shape = runtime_trace.response_body_shape(body, base64_encoded=base64_encoded)
    raw = body
    if base64_encoded:
        try:
            raw = base64.b64decode(body, validate=True).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            return shape, False, False, False
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return shape, False, False, False
    if not isinstance(payload, dict):
        return shape, False, False, False
    return (
        shape,
        isinstance(payload.get("post-target"), str) and bool(payload.get("post-target")),
        isinstance(payload.get("poll-result"), str) and bool(payload.get("poll-result")),
        isinstance(payload.get("ugc-track-id"), str) and bool(payload.get("ugc-track-id")),
    )


def _observe_stage1_network(
    client: cdp.CdpClient,
    *,
    expected_origin: str,
    duration: float = 1.5,
) -> _Stage1NetworkObservation:
    """Drain sanitized evidence for the one stage-one fetch already initiated."""
    observation = _Stage1NetworkObservation()
    request_methods: dict[str, str] = {}
    post_request_ids: set[str] = set()
    deadline = time.monotonic() + max(0.05, min(float(duration), 5.0))

    while time.monotonic() < deadline:
        message = client.recv_event(timeout=min(0.25, max(0.05, deadline - time.monotonic())))
        if message is None:
            continue
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        request_id = str(params.get("requestId") or "")

        if method == "Network.requestWillBeSent":
            request = params.get("request") if isinstance(params.get("request"), dict) else {}
            if not _is_stage1_url(request.get("url"), expected_origin=expected_origin):
                continue
            request_method = str(request.get("method") or "").upper()
            if request_id:
                request_methods[request_id] = request_method
            if request_method == "POST":
                observation.post_request_observed = True
                if request_id:
                    post_request_ids.add(request_id)
            elif request_method == "OPTIONS":
                observation.preflight_request_observed = True
            continue

        if method == "Network.responseReceived":
            response = params.get("response") if isinstance(params.get("response"), dict) else {}
            if not _is_stage1_url(response.get("url"), expected_origin=expected_origin):
                continue
            status = int(response.get("status")) if isinstance(response.get("status"), (int, float)) else None
            request_method = request_methods.get(request_id)
            if request_method == "POST":
                observation.post_http_status = status
            elif request_method == "OPTIONS":
                observation.preflight_http_status = status
            continue

        if method == "Network.loadingFailed" and request_id in request_methods:
            request_method = request_methods.get(request_id)
            if request_method == "POST":
                observation.post_loading_failed = True
            elif request_method == "OPTIONS":
                observation.preflight_loading_failed = True
            blocked_reason = _safe_policy_label(params.get("blockedReason"))
            if blocked_reason:
                observation.blocked_reason = blocked_reason
            cors_status = params.get("corsErrorStatus") if isinstance(params.get("corsErrorStatus"), dict) else {}
            cors_error = _safe_policy_label(cors_status.get("corsError"))
            if cors_error:
                observation.cors_error = cors_error
            continue

        if method == "Network.loadingFinished" and request_id in post_request_ids:
            try:
                body_result = client.call("Network.getResponseBody", {"requestId": request_id}, timeout=2.0)
            except cdp.CdpProbeError:
                continue
            shape, post_target, poll_result, ugc_track_id = _decode_stage1_body(body_result)
            observation.response_shape = shape
            observation.post_target_present = post_target
            observation.poll_result_present = poll_result
            observation.ugc_track_id_present = ugc_track_id

    return observation


def _network_observation_payload(observation: _Stage1NetworkObservation) -> dict[str, Any]:
    return {
        "postRequestObserved": observation.post_request_observed,
        "preflightRequestObserved": observation.preflight_request_observed,
        "postHttpStatus": observation.post_http_status,
        "preflightHttpStatus": observation.preflight_http_status,
        "postLoadingFailed": observation.post_loading_failed,
        "preflightLoadingFailed": observation.preflight_loading_failed,
        "blockedReason": observation.blocked_reason,
        "corsError": observation.cors_error,
        "responseBodyShape": _safe_shape(observation.response_shape),
    }


def _diagnosis(value: dict[str, Any], observation: _Stage1NetworkObservation | None = None) -> str:
    network = observation or _Stage1NetworkObservation()
    runtime_completed = bool(value.get("networkCompleted"))
    runtime_status = int(value.get("httpStatus") or 0) if runtime_completed else None
    status = runtime_status if runtime_status is not None else network.post_http_status
    post_target_present = bool(value.get("postTargetPresent")) or network.post_target_present

    if status is not None and 200 <= status <= 299 and post_target_present:
        return "python-transport-mismatch-confirmed"
    if status in {401, 403}:
        return "credential-or-required-request-profile-rejected"
    if network.cors_error or network.blocked_reason:
        return "chromium-renderer-policy-blocked-stage1"
    if network.preflight_request_observed and not network.post_request_observed:
        return "chromium-cors-preflight-blocked-stage1"
    if status is not None:
        return "chromium-network-path-confirmed-without-upload-slot"
    if not runtime_completed:
        return "chromium-network-path-failed"
    return "chromium-network-path-confirmed-without-upload-slot"


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if not args.confirm_prepare:
        raise YandexUploadProtocolError("CDP OAuth probe requires --confirm-prepare.")
    if not args.confirm_owned_file:
        raise YandexUploadProtocolError("CDP OAuth probe requires --confirm-owned-file.")
    if args.port <= 0 or args.port > 65535:
        raise YandexUploadProtocolError("CDP port must be a valid TCP port.")

    base_dir = Path(args.base_dir) if args.base_dir else None
    live._require_research_opt_in(base_dir)  # noqa: SLF001 - shared research safety gate.
    context = _cached_stage1_context(args, base_dir)

    token = live._saved_token(base_dir)  # noqa: SLF001 - existing credential boundary; never returned.
    requester = YandexOAuthStage1Requester(
        base_url=args.stage1_base_url,
        oauth_token=token,
        transport_mode="http2",
        client_profile="desktop",
        trust_env=False,
    )
    params = {
        "uid": context.uid,
        "playlist-id": context.playlist_id,
        "path": live._stage1_path(context.file_path, args.path_mode),  # noqa: SLF001
    }
    endpoint = f"{requester.sanitized_origin}{_STAGE1_PATH}?{urlencode(params)}"

    groundtruth._launch_desktop(args.launch_exe, port=args.port, wait_seconds=args.launch_wait)  # noqa: SLF001
    target = groundtruth._discover_target(  # noqa: SLF001
        args.port,
        args.target_contains,
        timeout=max(5.0, args.launch_wait + 2.0),
    )
    websocket_url = str(target.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        raise YandexUploadProtocolError("Selected desktop target has no DevTools WebSocket URL.")

    expression = _expression(endpoint=endpoint, oauth_token=token)
    observation = _Stage1NetworkObservation()
    try:
        with cdp.CdpClient(websocket_url) as cdp_client:
            cdp_client.call("Network.enable")
            cdp_client.call("Runtime.enable")
            result = cdp_client.call(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
                timeout=args.timeout,
            )
            observation = _observe_stage1_network(
                cdp_client,
                expected_origin=requester.sanitized_origin,
            )
    except cdp.CdpProbeError as exc:
        raise YandexUploadProtocolError(f"Chromium OAuth stage-one probe failed: {exc}") from exc
    except OSError as exc:
        raise YandexUploadProtocolError(
            f"Chromium OAuth stage-one probe failed with local I/O error ({type(exc).__name__})."
        ) from exc

    value = _runtime_value(result)
    runtime_completed = bool(value.get("networkCompleted"))
    runtime_http_status = int(value.get("httpStatus") or 0) if runtime_completed else None
    http_status = runtime_http_status if runtime_http_status is not None else observation.post_http_status
    upload_url_present = bool(value.get("postTargetPresent")) or observation.post_target_present
    poll_url_present = bool(value.get("pollResultPresent")) or observation.poll_result_present
    track_id_present = bool(value.get("ugcTrackIdPresent")) or observation.ugc_track_id_present
    response_shape = _safe_shape(value.get("responseShape"))
    if response_shape.get("type") == "unavailable" and observation.response_shape is not None:
        response_shape = _safe_shape(observation.response_shape)

    diagnosis = _diagnosis(value, observation)
    verified_slot = bool(http_status is not None and 200 <= http_status <= 299 and upload_url_present)
    stage1_post_observed = bool(observation.post_request_observed or runtime_completed)

    payload = {
        "format": _FORMAT,
        "mode": "prepare",
        "status": "upload_url_obtained" if verified_slot else "diagnostic_complete",
        "diagnosis": diagnosis,
        "network": {
            "stage1Sent": stage1_post_observed,
            "stage1PostObservedByCdp": observation.post_request_observed,
            "corsPreflightObservedByCdp": observation.preflight_request_observed,
            "stage2Sent": False,
            "chromiumNetworkStack": True,
            "browserCredentialsMode": "omit",
        },
        "playlist": {
            "kind": str(args.playlist_kind),
            "playlistIdSourceRequested": args.playlist_id_source,
            "playlistIdSourceUsed": context.playlist_id_source,
            "playlistIdDiagnosticFallback": context.playlist_id_fallback,
            "contextSource": "musicark-local-cache",
            "observedVisibility": context.observed_visibility,
        },
        "file": live._file_summary(context.file_path),  # noqa: SLF001
        "stage1": {
            "origin": requester.sanitized_origin,
            "rendererFetchCompleted": runtime_completed,
            "httpResponseReceived": http_status is not None,
            "httpStatus": http_status,
            "uploadUrlPresent": upload_url_present,
            "pollUrlPresent": poll_url_present,
            "trackIdPresent": track_id_present,
            "responseShape": response_shape,
            "authorizationSource": "musicark-saved-oauth",
            "desktopSessionCredentialsAttached": False,
            "pythonYandexClientInitialized": False,
            "cdpNetwork": _network_observation_payload(observation),
        },
        "probe": {
            "mutation": "stage1-upload-slot-only",
            "rawCdpPersisted": False,
            "automaticRetry": False,
        },
        "safety": {
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "raw_cdp_messages_included": False,
            "cdp_request_ids_included": False,
            "cors_failed_parameter_included": False,
            "audio_bytes_sent": False,
        },
    }
    if not runtime_completed:
        payload["stage1"]["networkErrorClass"] = str(value.get("errorName") or "Error")[:80]
    return payload, (0 if verified_slot else 3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send one stage-one-only MusicArk OAuth request through the official desktop Chromium network stack."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--file", required=True)
    parser.add_argument("--playlist-kind", required=True)
    parser.add_argument("--stage1-base-url", required=True)
    parser.add_argument("--playlist-id-source", choices=("uuid", "kind"), default="uuid")
    parser.add_argument("--path-mode", choices=("full", "name"), default="full")
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-prepare", action="store_true")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--target-contains", default="Yandex")
    parser.add_argument("--launch-exe", type=Path, default=None)
    parser.add_argument("--launch-wait", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.launch_wait < 0 or args.launch_wait > 60:
        raise SystemExit("--launch-wait must be between 0 and 60 seconds")
    if args.timeout <= 0 or args.timeout > 120:
        raise SystemExit("--timeout must be between 0 and 120 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - safe CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())