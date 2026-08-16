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


class _DirectCoverageProxy:
    """Present direct user intent to DownloadService without mutating triage state.

    DownloadService historically uses `userAction=wanted` as its safety gate. A
    direct click on `Скачать` is already explicit user intent, so the bridge marks
    the persisted task as `direct_request` and presents a transient wanted view only
    to the service while that task is executed/retried. The real Coverage action in
    SQLite remains untouched (`unreviewed`, `ignored`, or `wanted`).
    """

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
    """Keep legacy/reference-cache tasks out of the v0.7 user queue surface."""
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
    # Ask for all rows and apply the v0.7 ownership discriminator here. Older
    # reference-acquisition rows share the table/provider but not source_provider_id.
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
    task = service._downloads.get_task(task_id)  # noqa: SLF001 - package bridge boundary.
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


def _user_summary(service: DownloadService) -> dict[str, Any]:
    items = _user_items(service, limit=5000)
    return {"counts": _summary_counts(items), "settings": service.settings()}


def _user_tasks(
    service: DownloadService,
    *,
    status: str,
    limit: int,
) -> dict[str, Any]:
    items = _user_items(service, status=status, limit=5000)
    items = items[: max(1, min(int(limit), 5000))]
    return {"count": len(items), "items": items}


def _direct_enqueue(service: DownloadService, external_id: str) -> dict[str, Any]:
    identity = str(external_id).strip()
    track = service._coverage.get_track(  # noqa: SLF001 - package bridge boundary.
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

    # Reuse the existing queue construction, but do not persist a fake triage
    # decision merely to satisfy its historical wanted gate.
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
        results.append(service._task_payload(task))  # noqa: SLF001 - same package boundary.
    return {"processed": len(results), "items": results}


def _user_clear_completed(service: DownloadService) -> dict[str, Any]:
    # Historical clear_completed predates v0.7 ownership and would also remove
    # reference-cache history. Restrict the UI action explicitly.
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
    # Recovery must not mutate legacy/reference rows either. New user downloads are
    # identifiable by task_type even when their raw source-provider payload is damaged.
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
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes failures.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
