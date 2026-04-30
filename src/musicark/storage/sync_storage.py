"""Storage for sync plans and operations."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError
from musicark.sync.models import SyncOperation, SyncOperationType, SyncPlan


class SyncStorageRepository:
    """Persists and restores sync plans."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def save_plan(self, plan: SyncPlan) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO sync_plans(id, created_at, dry_run, summary_json, status)
                        VALUES (?, ?, ?, ?, 'planned')
                        ON CONFLICT(id) DO UPDATE SET
                            summary_json=excluded.summary_json,
                            dry_run=excluded.dry_run
                        """,
                        (
                            plan.id,
                            plan.created_at,
                            1 if plan.dry_run else 0,
                            json.dumps(plan.summary, ensure_ascii=False),
                        ),
                    )
                    conn.execute("DELETE FROM sync_operations WHERE plan_id=?", (plan.id,))
                    for op in plan.operations:
                        conn.execute(
                            """
                            INSERT INTO sync_operations(
                                plan_id, operation_type, entity_id, reason, confidence, is_dangerous, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                plan.id,
                                op.operation_type.value,
                                op.entity_id,
                                op.reason,
                                op.confidence,
                                1 if op.is_dangerous else 0,
                                json.dumps(op.metadata, ensure_ascii=False),
                            ),
                        )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist sync plan.") from exc

    def get_plan(self, plan_id: str) -> SyncPlan:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                header = conn.execute(
                    "SELECT id, created_at, dry_run, summary_json FROM sync_plans WHERE id=?",
                    (plan_id,),
                ).fetchone()
                if header is None:
                    raise StorageError(f"Sync plan '{plan_id}' not found.")
                rows = conn.execute(
                    """
                    SELECT operation_type, entity_id, reason, confidence, is_dangerous, metadata_json
                    FROM sync_operations
                    WHERE plan_id=?
                    ORDER BY id
                    """,
                    (plan_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read sync plan.") from exc

        operations = [
            SyncOperation(
                operation_type=SyncOperationType(row[0]),
                entity_id=row[1],
                reason=row[2],
                confidence=float(row[3]),
                is_dangerous=bool(row[4]),
                metadata=json.loads(row[5] or "{}"),
            )
            for row in rows
        ]
        return SyncPlan(
            id=header[0],
            created_at=header[1],
            dry_run=bool(header[2]),
            operations=operations,
            summary=json.loads(header[3] or "{}"),
        )

    def cancel_plan(self, plan_id: str) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute("UPDATE sync_plans SET status='cancelled' WHERE id=?", (plan_id,))
        except sqlite3.Error as exc:
            raise StorageError("Failed to cancel sync plan.") from exc
