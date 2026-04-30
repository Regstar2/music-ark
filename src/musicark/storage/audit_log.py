"""Minimal audit logger that records state-changing operations."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError


@dataclass(slots=True)
class AuditEvent:
    """Represents a single auditable operation outcome."""

    event_type: str
    entity_type: str
    entity_id: str | None
    status: str
    details: str | None = None


class AuditLogRepository:
    """Writes audit events to storage without owning business logic."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def append(self, event: AuditEvent) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO audit_log(event_type, entity_type, entity_id, status, details)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            event.event_type,
                            event.entity_type,
                            event.entity_id,
                            event.status,
                            event.details,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to append audit event.") from exc
