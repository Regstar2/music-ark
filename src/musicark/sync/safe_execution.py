"""Execute only validated safe sync-plan operations (v1.0 desktop MVP).

Safe path implemented: ``CREATE_DOWNLOAD_TASK`` for ``yandex_download`` /
``yandex_music_download``. Dangerous planner rows are skipped, never executed.
"""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.download.provider import LocalImportProvider, YandexMusicDownloadProvider
from musicark.download.system import DownloadSystem, DownloadSystemError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository

from .models import SyncOperationType


def resolve_latest_plan_id(database_path: Path) -> str | None:
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            row = conn.execute(
                """
                SELECT id FROM sync_plans
                WHERE status!='cancelled'
                ORDER BY datetime(created_at) DESC LIMIT 1
                """
            ).fetchone()
            return str(row[0]) if row else None
    except sqlite3.Error:
        return None


class SyncSafeExecutor:
    """Applies planner operations that MusicArk classifies as safe for v1.0 MVP."""

    def __init__(self, *, database_path: Path, base_dir: Path | None) -> None:
        self._database_path = Path(database_path)
        self._base_dir = base_dir
        self._sync_storage = SyncStorageRepository(self._database_path)
        self._audit = AuditLogRepository(self._database_path)

    def _download_system(self) -> DownloadSystem:
        system = DownloadSystem(self._database_path)
        system.register_provider(LocalImportProvider())
        system.register_provider(YandexMusicDownloadProvider(base_dir=self._base_dir))
        return system

    def execute_safe_plan_operations(
        self,
        *,
        plan_id: str | None,
        confirm: bool,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise ValueError('Safe sync execution requires {"confirm": true}.')

        pid = plan_id or resolve_latest_plan_id(self._database_path)
        if pid is None:
            raise StorageError("No sync plan exists. Run sync_plan first.")

        plan = self._sync_storage.get_plan(pid)
        ds = self._download_system()
        downloads = DownloadStorageRepository(self._database_path)

        executed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for op in plan.operations:
            if op.is_dangerous:
                skipped.append(
                    {
                        "operation_type": op.operation_type.value,
                        "entity_id": op.entity_id,
                        "reason": "dangerous_skipped",
                    }
                )
                continue

            if op.operation_type != SyncOperationType.CREATE_DOWNLOAD_TASK:
                skipped.append(
                    {
                        "operation_type": op.operation_type.value,
                        "entity_id": op.entity_id,
                        "reason": "not_executable_in_safe_v1",
                    }
                )
                continue

            md = dict(op.metadata or {})
            task_type = str(md.get("task_type") or "").strip()
            provider_id = str(md.get("provider_id") or "").strip()
            source_id = str(md.get("source_id") or op.entity_id).strip()
            target_folder = str(md.get("target_folder") or ".musicark/downloads/yandex")

            if task_type != "yandex_download" or provider_id != "yandex_music_download":
                skipped.append(
                    {
                        "operation_type": op.operation_type.value,
                        "entity_id": op.entity_id,
                        "reason": "unsupported_combo",
                        "task_type": task_type,
                        "provider_id": provider_id,
                    }
                )
                continue

            try:
                task = ds.create_task(
                    task_type=task_type,
                    source_id=source_id,
                    provider_id=provider_id,
                    target_folder=target_folder,
                )
                quality = md.get("quality", "best")
                task.raw_payload = {"track_id": source_id, "quality": str(quality)}
                downloads.upsert_task(task)

                finished = ds.run_task(task.id)
                executed.append(
                    {
                        "task_id": task.id,
                        "source_id": source_id,
                        "status": str(finished.status),
                    }
                )
                self._audit.append(
                    AuditEvent(
                        event_type="sync_safe_execute_download",
                        entity_type="sync_plan",
                        entity_id=str(pid),
                        status="success",
                        details=(
                            f"task_id={task.id} external_id={source_id} "
                            f"download_status={finished.status}"
                        )[:16000],
                    )
                )
            except (DownloadSystemError, OSError, ValueError, TypeError) as exc:
                errors.append({"source_id": source_id, "error": str(exc)})
                self._audit.append(
                    AuditEvent(
                        event_type="sync_safe_execute_download",
                        entity_type="sync_plan",
                        entity_id=str(pid),
                        status="failed",
                        details=f"source_id={source_id} error={exc}"[:16000],
                    )
                )

        summary = {
            "plan_id": str(pid),
            "executed_count": len(executed),
            "skipped_count": len(skipped),
            "error_count": len(errors),
        }
        self._audit.append(
            AuditEvent(
                event_type="sync_execute_safe_finished",
                entity_type="sync_plan",
                entity_id=str(pid),
                status="success" if not errors else "partial",
                details=json.dumps({"summary": summary}, ensure_ascii=False)[:16000],
            )
        )
        return {"summary": summary, "executed": executed, "skipped": skipped, "errors": errors}
