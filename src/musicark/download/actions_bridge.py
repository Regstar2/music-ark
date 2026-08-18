"""Batch actions for the user-facing Downloads workspace.

This bridge keeps bulk operations inside one Python process while preserving the
existing DownloadService invariants. Removing a task deletes only queue/history
state; final audio files, Local Library rows, Coverage state and matching data are
not deleted here.
"""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Callable

from musicark.download.models import DownloadStatus

from .bridge import _retry_user_task, _user_run_one
from .service import DownloadService, DownloadServiceError


_USER_TASK_TYPE = "provider_download"
_REMOVABLE_STATUSES = {DownloadStatus.FAILED, DownloadStatus.NEEDS_REVIEW}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-download-actions-bridge")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--batch-file", required=True)
    parser.add_argument(
        "command",
        choices=(
            "retry_tasks",
            "cancel_tasks",
            "remove_tasks",
            "run_tasks",
            "enqueue_selected",
        ),
    )
    return parser


def _load_batch(path: str) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DownloadServiceError("Invalid batch payload.", code="invalid_request") from exc
    if not isinstance(raw, dict):
        raise DownloadServiceError("Invalid batch payload.", code="invalid_request")
    return raw


def _clean_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = str(item).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _error_payload(exc: Exception, identity: str) -> dict[str, str]:
    code = exc.code if isinstance(exc, DownloadServiceError) else "unexpected_error"
    return {"id": identity, "code": code, "message": str(exc)}


def _batch_result(
    requested: list[str],
    items: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    skipped = sum(1 for item in items if str(item.get("status") or "") == "skipped")
    return {
        "requested": len(requested),
        "processed": len(items) + len(errors),
        "succeeded": max(0, len(items) - skipped),
        "failed": len(errors),
        "skipped": skipped,
        "items": items,
        "errors": errors,
    }


class DownloadTaskActions:
    """Perform explicit user task actions without widening DownloadService semantics."""

    def __init__(self, service: DownloadService) -> None:
        self._service = service

    def retry_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        return self._task_batch(task_ids, self._retry_one)

    def cancel_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        return self._task_batch(task_ids, self._cancel_one)

    def run_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        return self._task_batch(task_ids, self._run_one)

    def remove_tasks(self, task_ids: list[str]) -> dict[str, Any]:
        return self._task_batch(task_ids, self._remove_one)

    def enqueue_selected(self, external_ids: list[str]) -> dict[str, Any]:
        requested = _clean_ids(external_ids)
        items: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for external_id in requested:
            try:
                result = self._service.enqueue(external_id)
                task = result.get("task")
                if not isinstance(task, dict):
                    raise DownloadServiceError(
                        "Download service returned an invalid task payload.",
                        code="invalid_state",
                    )
                items.append(dict(task))
            except Exception as exc:  # noqa: BLE001 - batch must report partial failures.
                errors.append(_error_payload(exc, external_id))
        return _batch_result(requested, items, errors)

    def _task_batch(
        self,
        task_ids: list[str],
        operation: Callable[[str], dict[str, Any]],
    ) -> dict[str, Any]:
        requested = _clean_ids(task_ids)
        valid, validation_errors = self._validate_user_tasks(requested)
        items: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = list(validation_errors)
        for task_id in requested:
            if task_id not in valid:
                continue
            try:
                items.append(operation(task_id))
            except Exception as exc:  # noqa: BLE001 - batch must report partial failures.
                errors.append(_error_payload(exc, task_id))
        return _batch_result(requested, items, errors)

    def _validate_user_tasks(
        self,
        task_ids: list[str],
    ) -> tuple[set[str], list[dict[str, str]]]:
        """Reject missing/internal tasks before any batch mutation begins."""
        if not task_ids:
            return set(), []
        valid: set[str] = set()
        errors: list[dict[str, str]] = []
        try:
            with closing(sqlite3.connect(self._service._database_path)) as conn:  # noqa: SLF001
                for task_id in task_ids:
                    row = conn.execute(
                        "SELECT task_type FROM download_tasks WHERE id=?",
                        (task_id,),
                    ).fetchone()
                    if row is None or str(row[0]) != _USER_TASK_TYPE:
                        errors.append(
                            {
                                "id": task_id,
                                "code": "invalid_task",
                                "message": "Download task is not available to the user Downloads workflow.",
                            }
                        )
                    else:
                        valid.add(task_id)
        except sqlite3.Error as exc:
            raise DownloadServiceError(
                "Failed to validate download tasks.",
                code="storage_error",
            ) from exc
        return valid, errors

    def _retry_one(self, task_id: str) -> dict[str, Any]:
        result = _retry_user_task(self._service, task_id)
        task = result.get("task")
        return dict(task) if isinstance(task, dict) else {"id": task_id}

    def _cancel_one(self, task_id: str) -> dict[str, Any]:
        result = self._service.cancel(task_id)
        task = result.get("task")
        return dict(task) if isinstance(task, dict) else {"id": task_id}

    def _run_one(self, task_id: str) -> dict[str, Any]:
        """Use the existing one-task bridge guard so another worker is never bypassed."""
        result = _user_run_one(self._service, task_id)
        task = result.get("task")
        return dict(task) if isinstance(task, dict) else {"id": task_id}

    def _remove_one(self, task_id: str) -> dict[str, Any]:
        task = self._service._downloads.get_task(task_id)  # noqa: SLF001
        if task.status not in _REMOVABLE_STATUSES:
            raise DownloadServiceError(
                "Only failed or needs-review downloads can be removed.",
                code="not_removable",
            )

        self._cleanup_partial(task)
        try:
            with closing(sqlite3.connect(self._service._database_path)) as conn:  # noqa: SLF001
                with conn:
                    cursor = conn.execute(
                        "DELETE FROM download_tasks WHERE id=? AND task_type=?",
                        (task_id, _USER_TASK_TYPE),
                    )
                    if int(cursor.rowcount) != 1:
                        raise DownloadServiceError(
                            "Download task was not removed.",
                            code="invalid_task",
                        )
        except sqlite3.Error as exc:
            raise DownloadServiceError(
                "Failed to remove download task.",
                code="storage_error",
            ) from exc

        self._service._audit_event(  # noqa: SLF001 - audit remains authoritative after history removal.
            "download_task_removed",
            "success",
            f"status={task.status.value} source={task.source_id}",
            task_id,
        )
        return {"id": task_id, "status": "removed"}

    @staticmethod
    def _cleanup_partial(task: Any) -> None:
        """Delete only the expected sibling .part file; never the final audio file."""
        target_filename = str(task.raw_payload.get("target_filename") or "").strip()
        if not target_filename:
            return
        try:
            target_folder = Path(task.target_folder).expanduser().resolve(strict=False)
            final_path = (target_folder / target_filename).resolve(strict=False)
            if final_path.parent != target_folder:
                return
            partial = final_path.with_name(final_path.name + ".part")
            if partial.parent != target_folder:
                return
            partial.unlink(missing_ok=True)
        except OSError:
            return


def _dispatch(args: argparse.Namespace, service: DownloadService) -> dict[str, Any]:
    batch = _load_batch(args.batch_file)
    actions = DownloadTaskActions(service)
    if args.command == "retry_tasks":
        return actions.retry_tasks(_clean_ids(batch.get("taskIds")))
    if args.command == "cancel_tasks":
        return actions.cancel_tasks(_clean_ids(batch.get("taskIds")))
    if args.command == "remove_tasks":
        return actions.remove_tasks(_clean_ids(batch.get("taskIds")))
    if args.command == "run_tasks":
        return actions.run_tasks(_clean_ids(batch.get("taskIds")))
    if args.command == "enqueue_selected":
        return actions.enqueue_selected(_clean_ids(batch.get("externalIds")))
    raise DownloadServiceError("Unsupported download action.", code="invalid_request")


def _error(exc: Exception) -> dict[str, Any]:
    code = exc.code if isinstance(exc, DownloadServiceError) else "unexpected_error"
    return {"error": {"code": code, "message": str(exc)}}


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    base_dir = Path(args.base_dir) if args.base_dir else None
    try:
        service = DownloadService(base_dir=base_dir)
        payload = _dispatch(args, service)
    except Exception as exc:  # noqa: BLE001 - process boundary normalizes all errors.
        print(json.dumps(_error(exc), ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
