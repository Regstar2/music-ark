"""Capture a value-free fingerprint of one successful official desktop stage-one upload request.

The official Yandex Music desktop application performs the user-confirmed upload.
MusicArk only observes the localhost Chromium DevTools Protocol stream. The probe
never emits query/header values, cookies, authorization data, request IDs, raw
CDP messages, response bodies, signed URLs, or audio bytes.

Unlike the generic runtime trace, this diagnostic correlates
``Network.requestWillBeSent`` with ``Network.requestWillBeSentExtraInfo`` so the
actual wire header-name set can be compared with MusicArk's failing Chromium
probe. Known stage-one query values are classified only by equality against
already-local context (cached uid, cached playlist UUID/kind, and selected file
full/name path); the values themselves never leave memory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import yandex_upload_cdp_playlist_uuid_probe as uuid_probe
import yandex_upload_cdp_probe as cdp
import yandex_upload_ground_truth_poc as groundtruth
import yandex_upload_runtime_trace as trace
from musicark.providers.yandex_upload_transport import YandexUploadProtocolError


_FORMAT = "musicark-yandex-upload-desktop-stage1-fingerprint-v1"
_STAGE1_PATH = "/loader/upload-url"
_NET_ERROR_RE = re.compile(r"^NET::ERR_[A-Z0-9_]{1,120}$")
_SAFE_PROTOCOL_RE = re.compile(r"^[A-Za-z0-9._/+:-]{1,40}$")


def _safe_net_error(value: Any) -> str | None:
    clean = str(value or "").strip().upper()
    if not clean:
        return None
    return clean if _NET_ERROR_RE.fullmatch(clean) else "unknown"


def _safe_protocol(value: Any) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    return clean if _SAFE_PROTOCOL_RE.fullmatch(clean) else "unknown"


def _stage1_url(value: Any) -> bool:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.path or "/") == _STAGE1_PATH


def _windows_path_key(value: str) -> str:
    return value.replace("/", "\\").strip().casefold()


def _query_fingerprint(
    url: str,
    *,
    uid: str,
    playlist_uuid: str,
    playlist_kind: str,
    file_path: Path,
    visibility: str | None,
) -> dict[str, Any]:
    try:
        pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    except ValueError:
        pairs = []
    values: dict[str, str] = {}
    names: list[str] = []
    for raw_name, raw_value in pairs:
        name = str(raw_name or "")
        if not name or name in values:
            continue
        names.append(name)
        values[name] = str(raw_value or "")

    uid_value = values.get("uid")
    playlist_value = values.get("playlist-id")
    path_value = values.get("path")
    visibility_value = values.get("visibility")

    if uid_value is None:
        uid_class = "missing"
    elif uid_value == uid:
        uid_class = "matches-cached-uid"
    else:
        uid_class = "other"

    if playlist_value is None:
        playlist_class = "missing"
    elif playlist_value == playlist_uuid:
        playlist_class = "matches-cached-uuid"
    elif playlist_value == playlist_kind:
        playlist_class = "matches-kind"
    else:
        playlist_class = "other"

    if path_value is None:
        path_class = "missing"
    elif _windows_path_key(path_value) == _windows_path_key(str(file_path)):
        path_class = "matches-full-path"
    elif _windows_path_key(path_value) == _windows_path_key(file_path.name):
        path_class = "matches-file-name"
    else:
        path_class = "other"

    if visibility_value is None:
        visibility_class = "missing"
    elif visibility is not None and visibility_value == visibility:
        visibility_class = "matches-cached-visibility"
    else:
        visibility_class = "present-other"

    return {
        "queryNames": sorted(names),
        "queryValueClasses": {
            "uid": uid_class,
            "playlist-id": playlist_class,
            "path": path_class,
            "visibility": visibility_class,
        },
    }


def _header_names(headers: Any) -> list[str]:
    return trace.header_names(headers)


@dataclass(slots=True)
class _RequestRecord:
    request_headers: list[str] = field(default_factory=list)
    wire_headers: list[str] = field(default_factory=list)
    response_headers: list[str] = field(default_factory=list)
    response_wire_headers: list[str] = field(default_factory=list)
    query: dict[str, Any] = field(default_factory=dict)
    resource_type: str | None = None
    has_post_data: bool = False
    http_status: int | None = None
    extra_info_status: int | None = None
    protocol: str | None = None
    loading_finished: bool = False
    loading_failure_code: str | None = None

    def payload(self) -> dict[str, Any]:
        request_set = set(self.request_headers)
        wire_set = set(self.wire_headers)
        return {
            **self.query,
            "rendererHeaderNames": self.request_headers,
            "wireHeaderNames": self.wire_headers,
            "wireOnlyHeaderNames": sorted(wire_set - request_set),
            "rendererOnlyHeaderNames": sorted(request_set - wire_set),
            "responseHeaderNames": self.response_headers,
            "responseWireHeaderNames": self.response_wire_headers,
            "resourceType": self.resource_type,
            "hasPostData": self.has_post_data,
            "httpStatus": self.http_status,
            "extraInfoStatus": self.extra_info_status,
            "responseProtocol": self.protocol,
            "loadingFinished": self.loading_finished,
            "loadingFailureCode": self.loading_failure_code,
            "headerPresence": {
                "authorization": "authorization" in wire_set or "authorization" in request_set,
                "cookie": "cookie" in wire_set or "cookie" in request_set,
                "accept-language": "accept-language" in wire_set or "accept-language" in request_set,
                "x-yandex-music-client": "x-yandex-music-client" in wire_set or "x-yandex-music-client" in request_set,
                "x-retry-count": "x-retry-count" in wire_set or "x-retry-count" in request_set,
                "x-request-id": "x-request-id" in wire_set or "x-request-id" in request_set,
                "x-yandex-music-device": "x-yandex-music-device" in wire_set or "x-yandex-music-device" in request_set,
                "x-yandex-music-without-invocation-info": (
                    "x-yandex-music-without-invocation-info" in wire_set
                    or "x-yandex-music-without-invocation-info" in request_set
                ),
            },
        }


class _FingerprintCollector:
    def __init__(
        self,
        *,
        uid: str,
        playlist_uuid: str,
        playlist_kind: str,
        file_path: Path,
        visibility: str | None,
    ) -> None:
        self._uid = uid
        self._playlist_uuid = playlist_uuid
        self._playlist_kind = playlist_kind
        self._file_path = file_path
        self._visibility = visibility
        self._records: dict[str, _RequestRecord] = {}
        self._pending_request_extra: dict[str, list[str]] = {}
        self._pending_response_extra: dict[str, tuple[list[str], int | None]] = {}

    def observe(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        request_id = str(params.get("requestId") or "")
        if not request_id:
            return

        if method == "Network.requestWillBeSent":
            request = params.get("request") if isinstance(params.get("request"), dict) else {}
            if str(request.get("method") or "").upper() != "POST" or not _stage1_url(request.get("url")):
                return
            record = _RequestRecord(
                request_headers=_header_names(request.get("headers")),
                query=_query_fingerprint(
                    str(request.get("url") or ""),
                    uid=self._uid,
                    playlist_uuid=self._playlist_uuid,
                    playlist_kind=self._playlist_kind,
                    file_path=self._file_path,
                    visibility=self._visibility,
                ),
                resource_type=str(params.get("type") or "")[:40] or None,
                has_post_data=bool(request.get("hasPostData")),
            )
            record.wire_headers = self._pending_request_extra.pop(request_id, [])
            pending_response = self._pending_response_extra.pop(request_id, None)
            if pending_response:
                record.response_wire_headers, record.extra_info_status = pending_response
            self._records[request_id] = record
            return

        if method == "Network.requestWillBeSentExtraInfo":
            names = _header_names(params.get("headers"))
            record = self._records.get(request_id)
            if record is not None:
                record.wire_headers = names
            else:
                self._pending_request_extra[request_id] = names
            return

        if method == "Network.responseReceived":
            record = self._records.get(request_id)
            if record is None:
                return
            response = params.get("response") if isinstance(params.get("response"), dict) else {}
            record.http_status = int(response.get("status")) if isinstance(response.get("status"), (int, float)) else None
            record.response_headers = _header_names(response.get("headers"))
            record.protocol = _safe_protocol(response.get("protocol"))
            return

        if method == "Network.responseReceivedExtraInfo":
            names = _header_names(params.get("headers"))
            status = int(params.get("statusCode")) if isinstance(params.get("statusCode"), (int, float)) else None
            record = self._records.get(request_id)
            if record is not None:
                record.response_wire_headers = names
                record.extra_info_status = status
            else:
                self._pending_response_extra[request_id] = (names, status)
            return

        record = self._records.get(request_id)
        if record is None:
            return
        if method == "Network.loadingFinished":
            record.loading_finished = True
        elif method == "Network.loadingFailed":
            record.loading_failure_code = _safe_net_error(params.get("errorText"))

    def successful(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for record in self._records.values():
            status = record.http_status if record.http_status is not None else record.extra_info_status
            if status is not None and 200 <= status <= 299:
                result.append(record.payload())
        return result

    def summary(self) -> dict[str, Any]:
        records = list(self._records.values())
        successful = self.successful()
        failed = [record for record in records if record.loading_failure_code]
        return {
            "observedStage1Posts": len(records),
            "successfulStage1Posts": len(successful),
            "failedStage1Posts": len(failed),
            "successfulFingerprint": successful[0] if successful else None,
        }


def _collect(
    websocket_url: str,
    *,
    duration: float,
    collector: _FingerprintCollector,
    started: threading.Event | None = None,
) -> None:
    try:
        with cdp.CdpClient(websocket_url) as client:
            client.call("Network.enable")
            if started is not None:
                started.set()
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                message = client.recv_event(timeout=min(0.5, max(0.05, deadline - time.monotonic())))
                if message is not None:
                    collector.observe(message)
                if collector.successful():
                    # Keep a short tail window so response ExtraInfo/loadingFinished can arrive.
                    tail = time.monotonic() + 1.0
                    while time.monotonic() < tail:
                        extra = client.recv_event(timeout=min(0.25, max(0.05, tail - time.monotonic())))
                        if extra is not None:
                            collector.observe(extra)
                    return
    except OSError as exc:
        raise YandexUploadProtocolError(
            f"Desktop fingerprint collection failed with local I/O error ({type(exc).__name__})."
        ) from exc
    except cdp.CdpProbeError as exc:
        raise YandexUploadProtocolError(f"Desktop fingerprint collection failed: {exc}") from exc


def run(args: argparse.Namespace, *, prompt=input) -> tuple[dict[str, Any], int]:  # noqa: ANN001
    if not args.confirm_owned_file:
        raise YandexUploadProtocolError("Desktop fingerprint probe requires --confirm-owned-file.")
    if not args.confirm_desktop_upload:
        raise YandexUploadProtocolError("Desktop fingerprint probe requires --confirm-desktop-upload.")
    if args.duration <= 0 or args.duration > 300:
        raise YandexUploadProtocolError("--duration must be between 0 and 300 seconds.")

    base_dir = Path(args.base_dir) if args.base_dir else None
    context = uuid_probe._uuid_context(args, base_dir)  # noqa: SLF001 - shared fail-closed local context.

    groundtruth._launch_desktop(args.launch_exe, port=args.port, wait_seconds=args.launch_wait)  # noqa: SLF001
    target = groundtruth._discover_target(  # noqa: SLF001
        args.port,
        args.target_contains,
        timeout=max(5.0, args.launch_wait + 2.0),
    )
    websocket_url = str(target.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        raise YandexUploadProtocolError("Selected desktop target has no DevTools WebSocket URL.")

    collector = _FingerprintCollector(
        uid=context.uid,
        playlist_uuid=context.playlist_id,
        playlist_kind=str(args.playlist_kind),
        file_path=context.file_path,
        visibility=context.observed_visibility,
    )

    started = threading.Event()
    holder: dict[str, Exception] = {}

    def worker() -> None:
        try:
            _collect(websocket_url, duration=args.duration, collector=collector, started=started)
        except Exception as exc:  # noqa: BLE001 - raised on caller thread after sanitization boundary.
            holder["error"] = exc
            started.set()

    thread = threading.Thread(target=worker, name="musicark-stage1-fingerprint", daemon=True)
    thread.start()
    if not started.wait(timeout=10.0):
        raise YandexUploadProtocolError("Desktop fingerprint collector did not arm within 10 seconds.")
    if "error" in holder:
        raise holder["error"]

    print(
        "Fingerprint collector is armed. In the official Yandex Music desktop UI, upload exactly the selected owned "
        "file to the selected playlist. Press Enter immediately after starting the visible desktop upload.",
        file=sys.stderr,
    )
    prompt("")
    thread.join(timeout=args.duration + 5.0)
    if thread.is_alive():
        raise YandexUploadProtocolError("Desktop fingerprint collector exceeded its bounded observation window.")
    if "error" in holder:
        raise holder["error"]

    summary = collector.summary()
    fingerprint = summary.get("successfulFingerprint")
    status = "captured" if isinstance(fingerprint, dict) else "no-successful-stage1-observed"

    payload = {
        "format": _FORMAT,
        "mode": "official-desktop-observation",
        "status": status,
        "playlist": {
            "kind": str(args.playlist_kind),
            "playlistIdContext": "cached-uuid",
            "playlistIdValueIncluded": False,
        },
        "file": {
            "name": context.file_path.name,
            "extension": context.file_path.suffix.lower(),
            "size": context.file_path.stat().st_size,
        },
        "stage1": summary,
        "probe": {
            "networkMutationInitiatedByProbe": False,
            "officialDesktopMutationConfirmedByUser": True,
            "rawCdpPersisted": False,
            "automaticRetry": False,
        },
        "safety": {
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "playlist_uuid_value_included": False,
            "uid_value_included": False,
            "path_value_included": False,
            "request_ids_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "raw_cdp_messages_included": False,
            "audio_bytes_sent_by_probe": False,
        },
    }
    return payload, (0 if status == "captured" else 3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a secret-free fingerprint of one successful official desktop stage-one upload request."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--file", required=True)
    parser.add_argument("--playlist-kind", required=True)
    parser.add_argument("--playlist-id-source", choices=("uuid",), default="uuid")
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-desktop-upload", action="store_true")
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--target-contains", default="Yandex")
    parser.add_argument("--launch-exe", type=Path, default=None)
    parser.add_argument("--launch-wait", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=120.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.port <= 0 or args.port > 65535:
        raise SystemExit("--port must be a valid TCP port")
    if args.launch_wait < 0 or args.launch_wait > 60:
        raise SystemExit("--launch-wait must be between 0 and 60 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - CLI boundary emits safe errors only.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
