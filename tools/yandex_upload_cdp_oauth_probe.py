"""Probe Yandex upload stage one through the official desktop Chromium network stack.

This diagnostic intentionally separates two remaining hypotheses after Python
``requests`` and HTTPX both observed a remote protocol close before any HTTP
status. The request is initiated by MusicArk through a localhost-only CDP
session, but Chromium/Electron performs the network operation.

The probe uses only the OAuth credential already stored by MusicArk and sends it
with ``credentials: 'omit'`` so browser cookies/session state are not attached.
It performs stage one only: no dynamic upload target is followed and no audio
bytes are sent. Raw CDP messages, OAuth values, query values, response bodies and
signed URLs are never written to disk or returned in the sanitized result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode

import yandex_upload_cdp_probe as cdp
import yandex_upload_ground_truth_poc as groundtruth
import yandex_upload_live_poc as live
from musicark.providers.yandex_upload_transport import (
    YandexOAuthStage1Requester,
    YandexUploadProtocolError,
)


_FORMAT = "musicark-yandex-upload-cdp-oauth-probe-v1"
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"


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


def _diagnosis(value: dict[str, Any]) -> str:
    if not bool(value.get("networkCompleted")):
        return "chromium-network-path-failed"
    status = int(value.get("httpStatus") or 0)
    if 200 <= status <= 299 and bool(value.get("postTargetPresent")):
        return "python-transport-mismatch-confirmed"
    if status in {401, 403}:
        return "credential-or-required-request-profile-rejected"
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
    client, playlist, file_path, uid, playlist_id, observed_visibility = live._prepare_context(args)  # noqa: SLF001
    del client

    token = live._saved_token(base_dir)  # noqa: SLF001 - existing credential boundary; never returned.
    requester = YandexOAuthStage1Requester(
        base_url=args.stage1_base_url,
        oauth_token=token,
        transport_mode="http2",
        client_profile="desktop",
        trust_env=False,
    )
    params = {
        "uid": uid,
        "playlist-id": playlist_id,
        "path": live._stage1_path(file_path, args.path_mode),  # noqa: SLF001
    }
    endpoint = f"{requester.sanitized_origin}/loader/upload-url?{urlencode(params)}"

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
    try:
        with cdp.CdpClient(websocket_url) as cdp_client:
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
    except cdp.CdpProbeError as exc:
        raise YandexUploadProtocolError(f"Chromium OAuth stage-one probe failed: {exc}") from exc
    except OSError as exc:
        raise YandexUploadProtocolError(
            f"Chromium OAuth stage-one probe failed with local I/O error ({type(exc).__name__})."
        ) from exc

    value = _runtime_value(result)
    network_completed = bool(value.get("networkCompleted"))
    http_status = int(value.get("httpStatus") or 0) if network_completed else None
    upload_url_present = bool(value.get("postTargetPresent"))
    diagnosis = _diagnosis(value)
    verified_slot = bool(network_completed and http_status is not None and 200 <= http_status <= 299 and upload_url_present)

    payload = {
        "format": _FORMAT,
        "mode": "prepare",
        "status": "upload_url_obtained" if verified_slot else "diagnostic_complete",
        "diagnosis": diagnosis,
        "network": {
            "stage1Sent": True,
            "stage2Sent": False,
            "chromiumNetworkStack": True,
            "browserCredentialsMode": "omit",
        },
        "playlist": {
            "kind": str(getattr(playlist, "kind", "")),
            "playlistIdSource": args.playlist_id_source,
            "observedVisibility": observed_visibility,
        },
        "file": live._file_summary(file_path),  # noqa: SLF001
        "stage1": {
            "origin": requester.sanitized_origin,
            "httpResponseReceived": network_completed,
            "httpStatus": http_status,
            "uploadUrlPresent": upload_url_present,
            "pollUrlPresent": bool(value.get("pollResultPresent")),
            "trackIdPresent": bool(value.get("ugcTrackIdPresent")),
            "responseShape": _safe_shape(value.get("responseShape")),
            "authorizationSource": "musicark-saved-oauth",
            "desktopSessionCredentialsAttached": False,
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
            "audio_bytes_sent": False,
        },
    }
    if not network_completed:
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
