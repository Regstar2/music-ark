"""Long-lived JSON-lines worker for user Yandex download tasks.

Flutter keeps this process alive while it walks a visible persisted queue. The
process owns one DownloadService and therefore one resilient Yandex provider /
client session instead of reinitializing Python and Client(token).init() for
every track. Input and output are one JSON object per line; credentials and
signed media URLs never cross this boundary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from musicark.download.models import DownloadStatus
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexTokenMissingError,
)

from .bridge import _error, _require_user_task_id, _user_run_one
from .service import DownloadService


_SYSTEMIC_FAILURE_LIMIT = 3
_SYSTEMIC_ERROR_CODES = {
    "network_error",
    "provider_network",
    "provider_timeout",
    "provider_request",
    "provider_unavailable",
    "rate_limited",
    "http_error",
}
_ALLOWED_REQUEST_KEYS = {"taskId"}


class WorkerCircuit:
    """Pause a queue before one systemic incident burns through thousands of rows."""

    def __init__(self, *, failure_limit: int = _SYSTEMIC_FAILURE_LIMIT) -> None:
        if failure_limit <= 0:
            raise ValueError("failure_limit must be positive")
        self.failure_limit = int(failure_limit)
        self.systemic_failure_streak = 0

    def observe(self, task: dict[str, Any]) -> dict[str, str] | None:
        status = str(task.get("status") or "")
        code = str(task.get("errorCode") or "")
        if status not in {
            DownloadStatus.FAILED.value,
            DownloadStatus.NEEDS_REVIEW.value,
        }:
            self.systemic_failure_streak = 0
            return None

        if code == "authentication":
            return {
                "code": "authentication",
                "reason": "authentication",
                "message": (
                    "Download queue paused after a Yandex Music authentication failure. "
                    "Re-authenticate and continue the queue."
                ),
            }

        if code in _SYSTEMIC_ERROR_CODES:
            self.systemic_failure_streak += 1
            if self.systemic_failure_streak >= self.failure_limit:
                return {
                    "code": "provider_paused",
                    "reason": "systemic_provider_failure",
                    "message": (
                        "Download queue paused after repeated Yandex Music provider/network failures. "
                        "Retry later or check network settings, then continue the queue."
                    ),
                }
            return None

        # Permanent per-track failures (unavailable, no download info, UGC,
        # invalid audio, etc.) do not indicate a provider-wide outage.
        self.systemic_failure_streak = 0
        return None

    def snapshot(self) -> dict[str, int]:
        return {"systemicFailureStreak": self.systemic_failure_streak}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-download-worker-bridge")
    parser.add_argument("--base-dir", default=None)
    return parser


def _invalid_request(message: str) -> dict[str, Any]:
    return {"error": {"code": "invalid_request", "message": message}}


def _safe_request(raw_line: str) -> tuple[str | None, dict[str, Any] | None]:
    try:
        value = json.loads(raw_line)
    except json.JSONDecodeError:
        return None, _invalid_request("Worker request must be valid JSON.")
    if not isinstance(value, dict):
        return None, _invalid_request("Worker request must be a JSON object.")
    unexpected = {str(key) for key in value} - _ALLOWED_REQUEST_KEYS
    if unexpected:
        return None, _invalid_request("Worker request contains unsupported fields.")
    task_id = str(value.get("taskId") or "").strip()
    if not task_id:
        return None, _invalid_request("taskId is required.")
    return task_id, None


def _write(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def run_worker(service: DownloadService) -> int:
    """Serve sequential task requests until stdin closes or the circuit pauses."""
    circuit = WorkerCircuit()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        task_id, request_error = _safe_request(line)
        if request_error is not None:
            _write(request_error)
            continue
        assert task_id is not None

        try:
            result = _user_run_one(service, _require_user_task_id(service, task_id))
            raw_task = result.get("task")
            if not isinstance(raw_task, dict):
                _write(_invalid_request("Download worker returned an invalid task payload."))
                continue
            task = dict(raw_task)
            pause = circuit.observe(task)
            payload = dict(result)
            payload["worker"] = circuit.snapshot()
            if pause is not None:
                payload["worker"].update(
                    {
                        "paused": True,
                        "pauseReason": pause["reason"],
                        "pauseCode": pause["code"],
                    }
                )
                payload["error"] = {
                    "code": pause["code"],
                    "message": pause["message"],
                }
                _write(payload)
                # Exit so a later explicit Continue starts a fresh provider/client
                # session (important after re-authentication or provider recovery).
                return 0
            payload["worker"].update(
                {"paused": False, "pauseReason": None, "pauseCode": None}
            )
            _write(payload)
        except Exception as exc:  # noqa: BLE001 - normalize at the process boundary.
            payload = _error(exc)
            _write(payload)
            if isinstance(exc, (YandexTokenMissingError, YandexAuthenticationError)):
                return 0
    return 0


def main() -> int:
    args = _parser().parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = DownloadService(base_dir=base_dir)
        return run_worker(service)
    except Exception as exc:  # noqa: BLE001
        _write(_error(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
