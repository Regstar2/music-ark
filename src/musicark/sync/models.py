"""Controlled Sync domain models for MusicArk v0.8."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class SyncOperationType(StrEnum):
    # Legacy values are intentionally preserved so historical plans remain readable.
    DOWNLOAD_TRACK = "download_track"
    MARK_UNAVAILABLE = "mark_unavailable"
    LINK_LOCAL = "link_local"
    NEEDS_REVIEW = "needs_review"
    UPDATE_METADATA_CANDIDATE = "update_metadata_candidate"
    UPLOAD_CANDIDATE = "upload_candidate"
    REPLACE_CANDIDATE = "replace_candidate"
    CREATE_DOWNLOAD_TASK = "create_download_task"

    # v0.8 production operations.
    ENQUEUE_DOWNLOAD = "enqueue_download"
    REVIEW_IDENTITY = "review_identity"
    REVIEW_VARIANT = "review_variant"
    USER_DECISION_REQUIRED = "user_decision_required"
    LOCAL_ONLY = "local_only"


class SyncOperationStatus(StrEnum):
    PENDING = "pending"
    ENQUEUED = "enqueued"
    SKIPPED = "skipped"
    FAILED = "failed"
    INFORMATIONAL = "informational"


class SyncPlanStatus(StrEnum):
    PLANNED = "planned"
    STALE = "stale"
    APPLIED = "applied"
    PARTIALLY_APPLIED = "partially_applied"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SyncScopeType(StrEnum):
    ALL = "all"
    LIKED = "liked"
    PLAYLIST = "playlist"
    LEGACY = "legacy"


@dataclass(slots=True, frozen=True)
class SyncOperation:
    """Single persisted operation from an immutable plan snapshot.

    ``status`` and ``result`` are execution metadata. They may change after the
    snapshot is created; the operation intent and metadata never do.
    """

    operation_type: SyncOperationType
    entity_id: str
    reason: str
    confidence: float = 0.0
    is_dangerous: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    operation_id: int | None = None
    status: SyncOperationStatus = SyncOperationStatus.INFORMATIONAL
    result: dict[str, Any] = field(default_factory=dict)
    updated_at: str | None = None


@dataclass(slots=True)
class SyncPlan:
    """Persisted dry-run snapshot used by Controlled Sync."""

    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    dry_run: bool = True
    operations: list[SyncOperation] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    planner_version: int = 1
    scope_type: SyncScopeType = SyncScopeType.ALL
    scope_id: str | None = None
    target_root_id: int | None = None
    target_folder: str | None = None
    input_fingerprint: str = ""
    status: SyncPlanStatus = SyncPlanStatus.PLANNED
    applied_at: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    @property
    def is_legacy(self) -> bool:
        return self.planner_version <= 0 or self.scope_type == SyncScopeType.LEGACY
