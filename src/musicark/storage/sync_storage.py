"""Persistence for legacy and v0.8 Controlled Sync plans."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.sync.models import (
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
    SyncPlan,
    SyncPlanStatus,
    SyncScopeType,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _loads(value: object) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


class SyncStorageRepository:
    """Persist immutable plan snapshots and mutable execution status."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def save_plan(self, plan: SyncPlan) -> None:
        """Insert a new snapshot. Existing v0.8 plans are never rewritten."""
        now = _now()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    exists = conn.execute(
                        "SELECT 1 FROM sync_plans WHERE id=?", (plan.id,)
                    ).fetchone()
                    if exists is not None:
                        raise StorageError(
                            f"Sync plan '{plan.id}' already exists; rebuild must create a new plan id."
                        )
                    conn.execute(
                        """
                        INSERT INTO sync_plans(
                            id, created_at, dry_run, summary_json, status,
                            planner_version, scope_type, scope_id,
                            target_root_id, target_folder, input_fingerprint,
                            applied_at, result_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            plan.id,
                            plan.created_at,
                            1 if plan.dry_run else 0,
                            json.dumps(plan.summary, ensure_ascii=False, sort_keys=True),
                            plan.status.value,
                            int(plan.planner_version),
                            plan.scope_type.value,
                            plan.scope_id,
                            plan.target_root_id,
                            plan.target_folder,
                            plan.input_fingerprint,
                            plan.applied_at,
                            json.dumps(plan.result, ensure_ascii=False, sort_keys=True),
                            now,
                        ),
                    )
                    for op in plan.operations:
                        conn.execute(
                            """
                            INSERT INTO sync_operations(
                                plan_id, operation_type, entity_id, reason, confidence,
                                is_dangerous, metadata_json, status, result_json, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                plan.id,
                                op.operation_type.value,
                                op.entity_id,
                                op.reason,
                                float(op.confidence),
                                1 if op.is_dangerous else 0,
                                json.dumps(op.metadata, ensure_ascii=False, sort_keys=True),
                                op.status.value,
                                json.dumps(op.result, ensure_ascii=False, sort_keys=True),
                                op.updated_at or now,
                            ),
                        )
        except sqlite3.IntegrityError as exc:
            raise StorageError("Failed to persist immutable sync plan.") from exc
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist sync plan.") from exc

    def get_plan(self, plan_id: str) -> SyncPlan:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                header = conn.execute(
                    """
                    SELECT id, created_at, dry_run, summary_json, status,
                           planner_version, scope_type, scope_id, target_root_id,
                           target_folder, input_fingerprint, applied_at, result_json
                    FROM sync_plans WHERE id=?
                    """,
                    (plan_id,),
                ).fetchone()
                if header is None:
                    raise StorageError(f"Sync plan '{plan_id}' not found.")
                rows = conn.execute(
                    """
                    SELECT id, operation_type, entity_id, reason, confidence,
                           is_dangerous, metadata_json, status, result_json, updated_at
                    FROM sync_operations
                    WHERE plan_id=? ORDER BY id
                    """,
                    (plan_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read sync plan.") from exc

        operations: list[SyncOperation] = []
        for row in rows:
            try:
                op_type = SyncOperationType(str(row[1]))
            except ValueError:
                # A future/unknown legacy operation must stay visible but never executable.
                op_type = SyncOperationType.NEEDS_REVIEW
                metadata = _loads(row[6])
                metadata["legacy_operation_type"] = str(row[1])
            else:
                metadata = _loads(row[6])
            try:
                op_status = SyncOperationStatus(str(row[7] or "informational"))
            except ValueError:
                op_status = SyncOperationStatus.INFORMATIONAL
            operations.append(
                SyncOperation(
                    operation_id=int(row[0]),
                    operation_type=op_type,
                    entity_id=str(row[2]),
                    reason=str(row[3]),
                    confidence=float(row[4] or 0.0),
                    is_dangerous=bool(row[5]),
                    metadata=metadata,
                    status=op_status,
                    result=_loads(row[8]),
                    updated_at=row[9],
                )
            )

        planner_version = int(header[5] or 0)
        try:
            scope_type = SyncScopeType(str(header[6] or "legacy"))
        except ValueError:
            scope_type = SyncScopeType.LEGACY
        try:
            status = SyncPlanStatus(str(header[4] or "planned"))
        except ValueError:
            status = SyncPlanStatus.PLANNED
        return SyncPlan(
            id=str(header[0]),
            created_at=str(header[1]),
            dry_run=bool(header[2]),
            operations=operations,
            summary=_loads(header[3]),
            planner_version=planner_version,
            scope_type=scope_type,
            scope_id=header[7],
            target_root_id=int(header[8]) if header[8] is not None else None,
            target_folder=str(header[9]) if header[9] is not None else None,
            input_fingerprint=str(header[10] or ""),
            status=status,
            applied_at=str(header[11]) if header[11] is not None else None,
            result=_loads(header[12]),
        )

    def list_plans(self, limit: int = 20) -> list[SyncPlan]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT id FROM sync_plans ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(int(limit), 100)),),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list sync plans.") from exc
        return [self.get_plan(str(row[0])) for row in rows]

    def latest_plan_id(self) -> str | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT id FROM sync_plans ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to resolve latest sync plan.") from exc
        return str(row[0]) if row else None

    def update_plan_state(
        self,
        plan_id: str,
        *,
        status: SyncPlanStatus,
        applied_at: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE sync_plans
                        SET status=?, applied_at=COALESCE(?, applied_at),
                            result_json=COALESCE(?, result_json), updated_at=?
                        WHERE id=?
                        """,
                        (
                            status.value,
                            applied_at,
                            json.dumps(result, ensure_ascii=False, sort_keys=True)
                            if result is not None
                            else None,
                            _now(),
                            plan_id,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise StorageError(f"Sync plan '{plan_id}' not found.")
        except sqlite3.Error as exc:
            raise StorageError("Failed to update sync plan state.") from exc

    def cancel_plan(self, plan_id: str) -> None:
        plan = self.get_plan(plan_id)
        if plan.status != SyncPlanStatus.PLANNED:
            raise StorageError("Only a planned sync plan can be cancelled.")
        self.update_plan_state(plan_id, status=SyncPlanStatus.CANCELLED)

    def update_operation_state(
        self,
        operation_id: int,
        *,
        status: SyncOperationStatus,
        result: dict[str, Any] | None = None,
    ) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE sync_operations
                        SET status=?, result_json=?, updated_at=? WHERE id=?
                        """,
                        (
                            status.value,
                            json.dumps(result or {}, ensure_ascii=False, sort_keys=True),
                            _now(),
                            int(operation_id),
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise StorageError(f"Sync operation '{operation_id}' not found.")
        except sqlite3.Error as exc:
            raise StorageError("Failed to update sync operation state.") from exc
