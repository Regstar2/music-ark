"""Run one unified official-desktop Yandex upload ground-truth experiment.

The tool combines three already-sanitized research boundaries:

1. local-only Chromium DevTools Protocol observation of the official desktop app;
2. one visible user-performed upload in that already-authenticated app;
3. MusicArk before/after playlist read-back verification.

It never accepts or persists OAuth/custom API tokens, cookies, sessions,
Authorization values, raw HAR/CDP messages, signed upload URLs, or browser
profiles. The official desktop application performs the upload mutation; MusicArk
only observes sanitized structure and verifies the resulting playlist identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable

import yandex_upload_cdp_probe as cdp
import yandex_upload_desktop_assisted_poc as assisted
import yandex_upload_ground_truth_analyzer as analyzer


def _instrumentation(path: Path | None) -> tuple[str | None, str | None]:
    if path is None:
        return None, None
    if not path.is_file():
        raise assisted.live.YandexUploadProtocolError("Runtime instrumentation file does not exist.")
    raw = path.read_bytes()
    return raw.decode("utf-8"), hashlib.sha256(raw).hexdigest()


def _launch_desktop(executable: Path | None, *, port: int, wait_seconds: float) -> None:
    if executable is None:
        return
    if not executable.is_file():
        raise assisted.live.YandexUploadProtocolError("Official Yandex Music executable does not exist.")
    subprocess.Popen(  # noqa: S603 - explicit local executable selected by the user.
        [
            str(executable),
            f"--remote-debugging-port={int(port)}",
            "--remote-allow-origins=http://localhost",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def _discover_target(port: int, contains: str | None, *, timeout: float) -> dict[str, Any]:
    """Wait for the local Electron renderer without exposing target details."""
    deadline = time.monotonic() + max(0.5, timeout)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return cdp.select_target(cdp.discover_targets(port), contains)
        except cdp.CdpProbeError as exc:
            last_error = exc
            time.sleep(0.25)
    detail = str(last_error) if isinstance(last_error, cdp.CdpProbeError) else "No attachable target became ready."
    raise assisted.live.YandexUploadProtocolError(f"Desktop CDP target discovery failed: {detail}")


def _preflight_cdp(websocket_url: str, instrumentation_source: str | None) -> None:
    """Validate and instrument CDP before asking the user to perform a mutation."""
    try:
        with cdp.CdpClient(websocket_url) as client:
            client.call("Network.enable")
            client.call("Runtime.enable")
            if instrumentation_source:
                client.call(
                    "Runtime.evaluate",
                    {"expression": instrumentation_source, "awaitPromise": False, "returnByValue": False},
                    timeout=10.0,
                )
    except cdp.CdpProbeError as exc:
        raise assisted.live.YandexUploadProtocolError(f"Desktop CDP preflight failed: {exc}") from exc
    except OSError as exc:
        raise assisted.live.YandexUploadProtocolError(
            f"Desktop CDP preflight failed with local I/O error ({type(exc).__name__})."
        ) from exc


def _safe_collector_error(exc: Exception) -> str:
    if isinstance(exc, cdp.CdpProbeError):
        return str(exc)
    if isinstance(exc, OSError):
        return f"local I/O error ({type(exc).__name__})"
    return type(exc).__name__


def _assisted_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        base_dir=args.base_dir,
        file=args.file,
        playlist_kind=args.playlist_kind,
        confirm_owned_file=args.confirm_owned_file,
        confirm_desktop_upload=args.confirm_desktop_upload,
        readback_attempts=args.readback_attempts,
        readback_delay=args.readback_delay,
        no_prompt=False,
    )


def combine_results(
    *,
    trace_report: dict[str, Any],
    ground_truth: dict[str, Any],
    assisted_payload: dict[str, Any],
) -> dict[str, Any]:
    """Combine only already-sanitized reports into the final PoC result."""
    readback = assisted_payload.get("readBack") if isinstance(assisted_payload.get("readBack"), dict) else {}
    verified = bool(readback.get("verified")) and not bool(readback.get("ambiguous"))
    return {
        "format": "musicark-yandex-upload-ground-truth-poc-v1",
        "transportMode": "official-desktop-assisted",
        "status": "verified" if verified else "uploaded_unverified",
        "stage1GroundTruth": ground_truth.get("stage1"),
        "runtimeGroundTruth": ground_truth.get("runtime"),
        "stage2GroundTruth": ground_truth.get("stage2"),
        "processingGroundTruth": ground_truth.get("processing"),
        "directHttpDecision": ground_truth.get("directHttpDecision"),
        "readBack": readback,
        "officialDesktopMutation": assisted_payload.get("mutation"),
        "trace": {
            "format": trace_report.get("format"),
            "eventCount": len(trace_report.get("events") or []),
            "rawCdpPersisted": bool((trace_report.get("probe") or {}).get("rawCdpPersisted")),
        },
        "safety": {
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "signed_urls_included": False,
            "raw_cdp_messages_included": False,
            "raw_response_bodies_included": False,
        },
    }


def _preflight_payload(target: dict[str, Any], instrumentation_sha256: str | None) -> dict[str, Any]:
    report = cdp.build_report(target, [], instrumentation_sha256=instrumentation_sha256)
    return {
        "format": "musicark-yandex-upload-cdp-preflight-v1",
        "mode": "cdp-preflight",
        "status": "ready",
        "target": report.get("target"),
        "instrumentationSha256": instrumentation_sha256,
        "probe": report.get("probe"),
        "safety": report.get("safety"),
    }


def run(args: argparse.Namespace, *, prompt: Callable[[str], str] = input) -> tuple[dict[str, Any], int]:
    if args.port <= 0 or args.port > 65535:
        raise assisted.live.YandexUploadProtocolError("CDP port must be a valid TCP port.")
    if args.trace_duration <= 0 or args.trace_duration > 900:
        raise assisted.live.YandexUploadProtocolError("Trace duration must be between 0 and 900 seconds.")
    if not args.preflight_only and (not args.file or not args.playlist_kind):
        raise assisted.live.YandexUploadProtocolError(
            "Full ground-truth PoC requires both --file and --playlist-kind."
        )

    _launch_desktop(args.launch_exe, port=args.port, wait_seconds=args.launch_wait)
    target = _discover_target(args.port, args.target_contains, timeout=max(5.0, args.launch_wait + 2.0))
    websocket_url = str(target.get("webSocketDebuggerUrl") or "")
    if not websocket_url:
        raise assisted.live.YandexUploadProtocolError("Selected desktop target has no DevTools WebSocket URL.")

    instrumentation_source, instrumentation_sha256 = _instrumentation(args.instrumentation_js)

    # Validate the complete CDP command path before the user uploads anything.
    # The instrumentation remains installed in the renderer after this short
    # preflight session, so the long-lived collector does not inject it twice.
    _preflight_cdp(websocket_url, instrumentation_source)
    if args.preflight_only:
        return _preflight_payload(target, instrumentation_sha256), 0

    holder: dict[str, Any] = {}
    collector_started = threading.Event()

    def collect() -> None:
        try:
            with cdp.CdpClient(websocket_url) as client:
                collector_started.set()
                events = cdp.collect_trace(
                    client,
                    duration=args.trace_duration,
                    instrumentation_source=None,
                )
            holder["trace"] = cdp.build_report(
                target,
                events,
                instrumentation_sha256=instrumentation_sha256,
            )
        except Exception as exc:  # noqa: BLE001 - sanitized below; no raw values are retained.
            holder["error"] = _safe_collector_error(exc)
            collector_started.set()

    collector = threading.Thread(target=collect, name="musicark-yandex-cdp", daemon=True)
    collector.start()
    if not collector_started.wait(timeout=10.0):
        raise assisted.live.YandexUploadProtocolError("Sanitized desktop trace collector did not start within 10 seconds.")
    if "error" in holder:
        raise assisted.live.YandexUploadProtocolError(
            f"Sanitized desktop trace collection failed before upload: {holder['error']}"
        )

    assisted_payload, assisted_code = assisted.run(_assisted_args(args), prompt=prompt)
    collector.join(timeout=args.trace_duration + 15.0)
    if collector.is_alive():
        raise assisted.live.YandexUploadProtocolError("Sanitized desktop trace did not finish within its bounded window.")
    if "error" in holder:
        raise assisted.live.YandexUploadProtocolError(f"Sanitized desktop trace collection failed: {holder['error']}")
    trace_report = holder.get("trace")
    if not isinstance(trace_report, dict):
        raise assisted.live.YandexUploadProtocolError("Sanitized desktop trace produced no report.")

    ground_truth = analyzer.analyze(trace_report)
    combined = combine_results(
        trace_report=trace_report,
        ground_truth=ground_truth,
        assisted_payload=assisted_payload,
    )

    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.write_text(json.dumps(trace_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.decision_output.parent.mkdir(parents=True, exist_ok=True)
    args.decision_output.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return combined, (0 if combined["status"] == "verified" else max(3, assisted_code))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Observe and verify one visible official Yandex Music desktop upload end-to-end."
    )
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--file", default=None)
    parser.add_argument("--playlist-kind", default=None)
    parser.add_argument("--confirm-owned-file", action="store_true")
    parser.add_argument("--confirm-desktop-upload", action="store_true")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate sanitized local CDP/runtime instrumentation and exit without any upload/read-back mutation.",
    )
    parser.add_argument("--port", type=int, default=9222)
    parser.add_argument("--target-contains", default="Yandex")
    parser.add_argument("--launch-exe", type=Path, default=None)
    parser.add_argument("--launch-wait", type=float, default=5.0)
    parser.add_argument("--trace-duration", type=float, default=120.0)
    parser.add_argument(
        "--instrumentation-js",
        type=Path,
        default=Path(__file__).with_name("yandex_upload_runtime_instrumentation.js"),
    )
    parser.add_argument("--readback-attempts", type=int, default=60)
    parser.add_argument("--readback-delay", type=float, default=2.0)
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path(".musicark/research/yandex-upload-runtime-ground-truth.json"),
    )
    parser.add_argument(
        "--decision-output",
        type=Path,
        default=Path(".musicark/research/yandex-upload-ground-truth-decision.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".musicark/research/yandex-upload-ground-truth-poc.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.readback_attempts < 1 or args.readback_attempts > 120:
        raise SystemExit("--readback-attempts must be between 1 and 120")
    if args.readback_delay < 0 or args.readback_delay > 10:
        raise SystemExit("--readback-delay must be between 0 and 10 seconds")
    if args.launch_wait < 0 or args.launch_wait > 60:
        raise SystemExit("--launch-wait must be between 0 and 60 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - safe CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
