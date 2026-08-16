"""JSON process bridge dedicated to the v0.7 user download workflow."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

from musicark.credentials import CredentialStoreError
from musicark.download.models import DownloadStatus
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)

from .service import DownloadService, DownloadServiceError


_USER_TASK_TYPE = "provider_download"
_USER_SOURCE_PROVIDER = "yandex_music"
_TERMINAL_HISTORY_LIMIT = 100
_ACTIVE_STATUSES = {"queued", "running", "failed", "needs_review"}


class _DirectCoverageProxy:
    """Present direct user intent to DownloadService without mutating triage state."""

    def __init__(self, repository: Any, external_id: str) -> None:
        self._repository = repository
        self._external_id = str(external_id)

    def get_track(self, *, provider_id: str, external_id: str) -> dict[str, Any] | None:
        item = self._repository.get_track(
            provider_id=provider_id,
            external_id=external_id,
        )
        if (
            item is not None
            and str(external_id) == self._external_id
            and item.get("coverageStatus") == "missing"
        ):
            item = dict(item)
            item["userAction"] = "wanted"
        return item

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-download-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument(
        "command",
        choices=(
            "summary",
            "tasks",
            "enqueue",
            "enqueue_wanted",
            "run",
            "run_task",
            "retry",
            "cancel",
            "clear_completed",
            "settings",
            "set_target",
            "recover",
        ),
    )
    parser.add_argument("--external-id", default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--status", default="")
    parser.add_argument("--limit", type=int, default=1000)
    return parser


def _required(value: str | None, name: str) -> str:
    clean = (value or "").strip()
    if not clean:
        raise DownloadServiceError(f"{name} is required.", code="invalid_request")
    return clean


def _is_user_item(item: dict[str, Any]) -> bool:
    return (
        str(item.get("provider") or "") == _USER_SOURCE_PROVIDER
        and str(item.get("downloadProvider") or "") == "yandex_music_download"
    )


def _user_items(
    service: DownloadService,
    *,
    status: str = "",
    limit: int = 5000,
) -> list[dict[str, Any]]:
    payload = service.tasks(status=status, limit=max(1, min(int(limit), 5000)))
    raw = payload.get("items")
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for value in raw:
        if not isinstance(value, dict):
            continue
        item = dict(value)
        if _is_user_item(item):
            items.append(item)
    return items


def _require_user_task_id(service: DownloadService, value: str | None) -> str:
    task_id = _required(value, "--task-id")
    task = service._downloads.get_task(task_id)  # noqa: SLF001
    if task.task_type != _USER_TASK_TYPE:
        raise DownloadServiceError(
            "This task belongs to an internal/legacy download workflow.",
            code="invalid_task",
        )
    return task_id


def _summary_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return {
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0) + counts.get("needs_review", 0),
        "cancelled": counts.get("cancelled", 0),
        "skipped": counts.get("skipped", 0),
        "total": sum(counts.values()),
    }


def _prune_user_completed_history(
    service: DownloadService,
    *,
    keep: int = _TERMINAL_HISTORY_LIMIT,
) -> int:
    """Bound successful task history; Local Library/audit remain authoritative."""
    keep_count = max(0, int(keep))
    try:
        with closing(sqlite3.connect(service._database_path)) as conn:  # noqa: SLF001
            with conn:
                if keep_count == 0:
                    cursor = conn.execute(
                        "DELETE FROM download_tasks WHERE status='completed' AND task_type=?",
                        (_USER_TASK_TYPE,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        DELETE FROM download_tasks
                        WHERE status='completed' AND task_type=?
                          AND id NOT IN (
                              SELECT id
                              FROM download_tasks
                              WHERE status='completed' AND task_type=?
                              ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
                              LIMIT ?
                          )
                        """,
                        (_USER_TASK_TYPE, _USER_TASK_TYPE, keep_count),
                    )
                return max(0, int(cursor.rowcount))
    except sqlite3.Error as exc:
        raise DownloadServiceError(
            "Failed to prune completed download history.", code="storage_error"
        ) from exc


def _user_summary(service: DownloadService) -> dict[str, Any]:
    _prune_user_completed_history(service)
    items = _user_items(service, limit=5000)
    return {"counts": _summary_counts(items), "settings": service.settings()}


def _user_tasks(
    service: DownloadService,
    *,
    status: str,
    limit: int,
) -> dict[str, Any]:
    clean_status = str(status or "").strip().casefold()
    if clean_status == "completed":
        _prune_user_completed_history(service)
    items = _user_items(service, status=clean_status, limit=5000)
    # The default Downloads page is operational state, not an unbounded archive.
    # Completed/cancelled/skipped rows are available only through explicit history filters.
    if not clean_status:
        items = [
            item
            for item in items
            if str(item.get("status") or "") in _ACTIVE_STATUSES
        ]
    items = items[: max(1, min(int(limit), 5000))]
    return {"count": len(items), "items": items}


def _direct_enqueue(service: DownloadService, external_id: str) -> dict[str, Any]:
    identity = str(external_id).strip()
    track = service._coverage.get_track(  # noqa: SLF001
        provider_id=service.SOURCE_PROVIDER,
        external_id=identity,
    )
    if track is None:
        raise DownloadServiceError(
            "Provider track is not present in the cached library.",
            code="track_missing",
        )
    if track.get("coverageStatus") != "missing":
        raise DownloadServiceError(
            "Only a currently Missing track can be downloaded directly.",
            code="not_eligible",
        )

    service_view = dict(track)
    service_view["userAction"] = "wanted"
    task, created = service._enqueue_track(service_view)  # noqa: SLF001
    task.raw_payload["direct_request"] = True
    service._downloads.upsert_task(task)  # noqa: SLF001
    return {"created": created, "task": service._task_payload(task)}  # noqa: SLF001


def _run_user_task(service: DownloadService, task_id: str):  # type: ignore[no-untyped-def]
    task = service._downloads.get_task(task_id)  # noqa: SLF001
    if not bool(task.raw_payload.get("direct_request")):
        return service.run_task(task_id)

    original = service._coverage  # noqa: SLF001
    service._coverage = _DirectCoverageProxy(original, task.source_id)  # noqa: SLF001
    try:
        return service.run_task(task_id)
    finally:
        service._coverage = original  # noqa: SLF001


def _retry_user_task(service: DownloadService, task_id: str) -> dict[str, Any]:
    task = service._downloads.get_task(task_id)  # noqa: SLF001
    if not bool(task.raw_payload.get("direct_request")):
        return service.retry(task_id)

    original = service._coverage  # noqa: SLF001
    service._coverage = _DirectCoverageProxy(original, task.source_id)  # noqa: SLF001
    try:
        return service.retry(task_id)
    finally:
        service._coverage = original  # noqa: SLF001


def _user_run_one(service: DownloadService, task_id: str) -> dict[str, Any]:
    """Run exactly one selected user task; never drain unrelated queued work."""
    running = _user_items(service, status="running", limit=2)
    if running and all(str(item.get("id") or "") != task_id for item in running):
        raise DownloadServiceError(
            "A download worker is already running.",
            code="worker_busy",
        )
    task = _run_user_task(service, task_id)
    pruned = _prune_user_completed_history(service)
    return {"task": service._task_payload(task), "historyPruned": pruned}  # noqa: SLF001


def _user_run(service: DownloadService) -> dict[str, Any]:
    if _user_items(service, status="running", limit=1):
        raise DownloadServiceError("A download worker is already running.", code="worker_busy")
    queued = sorted(
        _user_items(service, status="queued", limit=5000),
        key=lambda item: str(item.get("createdAt") or ""),
    )
    results: list[dict[str, Any]] = []
    for item in queued:
        task_id = str(item.get("id") or "").strip()
        if not task_id:
            continue
        task = _run_user_task(service, task_id)
        results.append(service._task_payload(task))  # noqa: SLF001
    pruned = _prune_user_completed_history(service)
    return {"processed": len(results), "items": results, "historyPruned": pruned}


def _user_clear_completed(service: DownloadService) -> dict[str, Any]:
    try:
        with closing(sqlite3.connect(service._database_path)) as conn:  # noqa: SLF001
            with conn:
                cursor = conn.execute(
                    "DELETE FROM download_tasks WHERE status='completed' AND task_type=?",
                    (_USER_TASK_TYPE,),
                )
                removed = max(0, int(cursor.rowcount))
    except sqlite3.Error as exc:
        raise DownloadServiceError(
            "Failed to clear completed user downloads.", code="storage_error"
        ) from exc
    return {"removed": removed}


def _user_recover(service: DownloadService) -> dict[str, Any]:
    recovered = 0
    for task in service._downloads.list_tasks(status="running", limit=5000):  # noqa: SLF001
        if task.task_type != _USER_TASK_TYPE:
            continue
        service._downloads._cleanup_partial(task)  # noqa: SLF001
        task.status = DownloadStatus.FAILED
        task.error_code = "interrupted"
        task.error_message = "Download was interrupted by application shutdown."
        task.finished_at = datetime.now(UTC).isoformat()
        task.cancel_requested = False
        service._downloads.upsert_task(task)  # noqa: SLF001
        recovered += 1
    return {"recovered": recovered}


def _dispatch(args: argparse.Namespace, service: DownloadService) -> dict[str, Any]:
    if args.command == "summary":
        return _user_summary(service)
    if args.command == "tasks":
        return _user_tasks(service, status=args.status, limit=args.limit)
    if args.command == "enqueue":
        return _direct_enqueue(service, _required(args.external_id, "--external-id"))
    if args.command == "enqueue_wanted":
        return service.enqueue_wanted()
    if args.command == "run":
        return _user_run(service)
    if args.command == "run_task":
        return _user_run_one(service, _require_user_task_id(service, args.task_id))
    if args.command == "retry":
        return _retry_user_task(service, _require_user_task_id(service, args.task_id))
    if args.command == "cancel":
        return service.cancel(_require_user_task_id(service, args.task_id))
    if args.command == "clear_completed":
        return _user_clear_completed(service)
    if args.command == "settings":
        return service.settings()
    if args.command == "set_target":
        path = os.getenv("MUSICARK_DOWNLOAD_TARGET", "").strip()
        if not path:
            raise DownloadServiceError("Download target path is missing.", code="invalid_request")
        return service.set_target(path)
    if args.command == "recover":
        return _user_recover(service)
    raise DownloadServiceError("Unsupported download command.", code="invalid_request")


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, DownloadServiceError):
        code = exc.code
    elif isinstance(exc, (YandexTokenMissingError, YandexAuthenticationError, CredentialStoreError)):
        code = "authentication"
    elif isinstance(exc, YandexMusicError):
        code = "provider_request"
    else:
        code = "unexpected_error"
    return {"error": {"code": code, "message": str(exc)}}


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = DownloadService(base_dir=base_dir)
        payload = _dispatch(args, service)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
