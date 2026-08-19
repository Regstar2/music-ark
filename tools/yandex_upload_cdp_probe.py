"""Collect a sanitized upload trace from the official Yandex Music desktop renderer.

The probe attaches only to a local Chromium/Electron DevTools endpoint. It never
writes raw CDP messages. Network events are sanitized immediately in memory and
only scheme/host/path, query/header names, status and structural response shapes
are persisted. The probe itself never triggers an upload or any Yandex mutation.

Typical local workflow:

1. close the existing Yandex Music desktop process;
2. start it with ``--remote-debugging-port=9222`` (or use ``--launch-exe``);
3. run this probe and perform one normal, visible upload in the official UI;
4. share only the generated sanitized JSON report.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen

import yandex_upload_runtime_trace as trace


DEFAULT_PORT = 9222
_UPLOAD_PATH_HINTS = ("loader/upload-url", "/ugc/", "upload")


class CdpProbeError(RuntimeError):
    """Raised when local Electron/Chromium debugging cannot be used safely."""


class _LocalWebSocket:
    """Minimal RFC6455 client sufficient for localhost Chrome DevTools Protocol."""

    def __init__(self, url: str, *, timeout: float = 2.0) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise CdpProbeError("Refusing non-local DevTools WebSocket URL.")
        self._host = parsed.hostname
        self._port = parsed.port or 80
        self._path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        self._timeout = float(timeout)
        self._socket: socket.socket | None = None
        self._fragment = bytearray()

    def connect(self) -> None:
        sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
        sock.settimeout(self._timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self._path or '/'} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: http://localhost\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._recv_until(sock, b"\r\n\r\n", 65536)
        first_line = response.split(b"\r\n", 1)[0]
        if b" 101 " not in first_line:
            sock.close()
            raise CdpProbeError("DevTools WebSocket handshake failed.")
        self._socket = sock

    @staticmethod
    def _recv_until(sock: socket.socket, marker: bytes, limit: int) -> bytes:
        data = bytearray()
        while marker not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise CdpProbeError("Unexpected EOF during WebSocket handshake.")
            data.extend(chunk)
            if len(data) > limit:
                raise CdpProbeError("WebSocket handshake exceeded safety limit.")
        return bytes(data)

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def settimeout(self, value: float) -> None:
        self._timeout = float(value)
        if self._socket is not None:
            self._socket.settimeout(self._timeout)

    def _recv_exact(self, count: int) -> bytes:
        if self._socket is None:
            raise CdpProbeError("WebSocket is not connected.")
        data = bytearray()
        while len(data) < count:
            chunk = self._socket.recv(count - len(data))
            if not chunk:
                raise CdpProbeError("Unexpected EOF from DevTools WebSocket.")
            data.extend(chunk)
        return bytes(data)

    def send_text(self, text: str) -> None:
        if self._socket is None:
            raise CdpProbeError("WebSocket is not connected.")
        payload = text.encode("utf-8")
        first = 0x81
        mask_bit = 0x80
        length = len(payload)
        header = bytearray([first])
        if length < 126:
            header.append(mask_bit | length)
        elif length <= 0xFFFF:
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._socket.sendall(bytes(header) + mask + masked)

    def recv_text(self) -> str | None:
        while True:
            head = self._recv_exact(2)
            first, second = head
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            if length > 32 * 1024 * 1024:
                raise CdpProbeError("Refusing oversized DevTools frame.")
            mask = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length)
            if mask:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

            if opcode == 0x8:
                return None
            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in {0x1, 0x0}:
                self._fragment.extend(payload)
                if not fin:
                    continue
                data = bytes(self._fragment)
                self._fragment.clear()
                return data.decode("utf-8", errors="replace")

    def _send_control(self, opcode: int, payload: bytes) -> None:
        if self._socket is None:
            return
        payload = payload[:125]
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._socket.sendall(bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked)


class CdpClient:
    def __init__(self, websocket_url: str) -> None:
        self._ws = _LocalWebSocket(websocket_url)
        self._next_id = 1
        self._backlog: list[dict[str, Any]] = []

    def __enter__(self) -> "CdpClient":
        self._ws.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self._ws.close()

    def _recv_json(self, *, timeout: float) -> dict[str, Any] | None:
        self._ws.settimeout(timeout)
        try:
            text = self._ws.recv_text()
        except socket.timeout:
            return None
        if text is None:
            return None
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def call(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 5.0) -> dict[str, Any]:
        call_id = self._next_id
        self._next_id += 1
        self._ws.send_text(json.dumps({"id": call_id, "method": method, "params": params or {}}, separators=(",", ":")))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self._recv_json(timeout=min(0.5, max(0.05, deadline - time.monotonic())))
            if message is None:
                continue
            if message.get("id") == call_id:
                if "error" in message:
                    raise CdpProbeError(f"CDP command failed: {method}")
                result = message.get("result")
                return result if isinstance(result, dict) else {}
            self._backlog.append(message)
        raise CdpProbeError(f"Timed out waiting for CDP command: {method}")

    def recv_event(self, *, timeout: float = 0.5) -> dict[str, Any] | None:
        if self._backlog:
            return self._backlog.pop(0)
        return self._recv_json(timeout=timeout)


def discover_targets(port: int) -> list[dict[str, Any]]:
    url = f"http://127.0.0.1:{int(port)}/json/list"
    try:
        with urlopen(url, timeout=2.0) as response:  # noqa: S310 - localhost-only URL above.
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts to safe error.
        raise CdpProbeError("Unable to reach local Chromium DevTools endpoint.") from exc
    if not isinstance(payload, list):
        raise CdpProbeError("Unexpected DevTools target list shape.")
    return [item for item in payload if isinstance(item, dict)]


def select_target(targets: list[dict[str, Any]], contains: str | None = None) -> dict[str, Any]:
    candidates = [item for item in targets if item.get("type") in {"page", "webview"} and item.get("webSocketDebuggerUrl")]
    if contains:
        needle = contains.lower()
        filtered = [
            item
            for item in candidates
            if needle in str(item.get("title") or "").lower() or needle in str(item.get("url") or "").lower()
        ]
        if filtered:
            candidates = filtered
    if not candidates:
        raise CdpProbeError("No attachable page/webview target found.")
    return candidates[0]


def _is_relevant(event: dict[str, Any]) -> bool:
    if event.get("event") == "runtime":
        return True
    path = str(event.get("path") or "").lower()
    host = str(event.get("host") or "").lower()
    method = str(event.get("method") or "").upper()
    if any(hint in path or hint in host for hint in _UPLOAD_PATH_HINTS):
        return True
    if event.get("contentTypeKind") == "multipart-form-data" and method == "POST":
        return True
    return False


def _safe_target_metadata(target: dict[str, Any]) -> dict[str, Any]:
    url = trace.sanitize_url(str(target.get("url") or ""))
    return {
        "type": str(target.get("type") or "unknown")[:40],
        "url": url,
        "titlePresent": bool(target.get("title")),
    }


def collect_trace(
    client: CdpClient,
    *,
    duration: float,
    instrumentation_source: str | None,
) -> list[dict[str, Any]]:
    client.call("Network.enable")
    client.call("Runtime.enable")
    if instrumentation_source:
        client.call(
            "Runtime.evaluate",
            {"expression": instrumentation_source, "awaitPromise": False, "returnByValue": False},
            timeout=10.0,
        )

    events: list[dict[str, Any]] = []
    stage1_requests: dict[str, dict[str, Any]] = {}
    pending_bodies: list[str] = []
    deadline = time.monotonic() + duration

    while time.monotonic() < deadline:
        message = client.recv_event(timeout=min(0.5, max(0.05, deadline - time.monotonic())))
        if message is None:
            continue
        method = message.get("method")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        sanitized = trace.sanitize_cdp_message(message)
        request_id = str(params.get("requestId") or "")

        if sanitized is not None and _is_relevant(sanitized):
            events.append(sanitized)
            if sanitized.get("event") == "request" and sanitized.get("path") == "/loader/upload-url" and request_id:
                stage1_requests[request_id] = {
                    "scheme": sanitized.get("scheme"),
                    "host": sanitized.get("host"),
                    "path": sanitized.get("path"),
                }

        if method == "Network.loadingFinished" and request_id in stage1_requests:
            pending_bodies.append(request_id)

        while pending_bodies:
            body_request_id = pending_bodies.pop(0)
            try:
                body_result = client.call("Network.getResponseBody", {"requestId": body_request_id}, timeout=3.0)
                body_shape = trace.response_body_shape(
                    str(body_result.get("body") or ""),
                    base64_encoded=bool(body_result.get("base64Encoded")),
                )
            except CdpProbeError:
                body_shape = {"type": "unavailable"}
            events.append(
                {
                    "event": "response-shape",
                    **stage1_requests.get(body_request_id, {}),
                    "bodyShape": body_shape,
                }
            )
            stage1_requests.pop(body_request_id, None)

    return events


def build_report(target: dict[str, Any], events: list[dict[str, Any]], *, instrumentation_sha256: str | None) -> dict[str, Any]:
    return {
        "format": "musicark-yandex-upload-cdp-runtime-report-v1",
        "source": "official-desktop-local-cdp-black-box",
        "target": _safe_target_metadata(target),
        "instrumentationSha256": instrumentation_sha256,
        "events": events,
        "probe": {"networkMutationInitiatedByProbe": False, "rawCdpPersisted": False},
        "safety": {
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
            "raw_cdp_messages_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a secret-free Yandex Music upload trace from local Electron CDP.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--duration", type=float, default=120.0, help="Seconds to observe while the user performs one visible official upload.")
    parser.add_argument("--target-contains", default="Yandex")
    parser.add_argument("--instrumentation-js", type=Path, default=Path(__file__).with_name("yandex_upload_runtime_instrumentation.js"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launch-exe", type=Path, default=None, help="Optional official Yandex Music executable to launch with remote debugging.")
    parser.add_argument("--launch-wait", type=float, default=5.0)
    args = parser.parse_args()

    if args.duration <= 0 or args.duration > 900:
        raise SystemExit("--duration must be between 0 and 900 seconds")
    if args.port <= 0 or args.port > 65535:
        raise SystemExit("--port must be a valid TCP port")

    process = None
    if args.launch_exe is not None:
        if not args.launch_exe.is_file():
            raise SystemExit("--launch-exe does not exist")
        process = subprocess.Popen(  # noqa: S603 - explicit local executable selected by user.
            [str(args.launch_exe), f"--remote-debugging-port={args.port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(max(0.0, min(args.launch_wait, 30.0)))

    instrumentation_source = None
    instrumentation_sha256 = None
    if args.instrumentation_js and args.instrumentation_js.is_file():
        instrumentation_source = args.instrumentation_js.read_text(encoding="utf-8")
        instrumentation_sha256 = hashlib.sha256(instrumentation_source.encode("utf-8")).hexdigest()

    try:
        targets = discover_targets(args.port)
        target = select_target(targets, args.target_contains)
        websocket_url = str(target.get("webSocketDebuggerUrl") or "")
        with CdpClient(websocket_url) as client:
            events = collect_trace(client, duration=args.duration, instrumentation_source=instrumentation_source)
        report = build_report(target, events, instrumentation_sha256=instrumentation_sha256)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote sanitized CDP upload report: {args.output}")
        return 0
    finally:
        # Do not terminate an official client launched for a visible/manual upload;
        # preserving the user's desktop state is less surprising than killing it.
        _ = process


if __name__ == "__main__":
    raise SystemExit(main())
