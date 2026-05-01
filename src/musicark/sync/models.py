"""Sync planner models for v0.8."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class SyncOperationType(StrEnum):
    DOWNLOAD_TRACK = "download_track"
    MARK_UNAVAILABLE = "mark_unavailable"
    LINK_LOCAL = "link_local"
    NEEDS_REVIEW = "needs_review"
    UPDATE_METADATA_CANDIDATE = "update_metadata_candidate"
    UPLOAD_CANDIDATE = "upload_candidate"
    REPLACE_CANDIDATE = "replace_candidate"
    CREATE_DOWNLOAD_TASK = "create_download_task"


@dataclass(slots=True, frozen=True)
class SyncOperation:
    """Single planned sync operation without execution side effects."""

    operation_type: SyncOperationType
    entity_id: str
    reason: str
    confidence: float = 0.0
    is_dangerous: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SyncPlan:
    """Saved dry-run sync plan."""

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    dry_run: bool = True
    operations: list[SyncOperation] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
