"""Download system models for v0.5."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class DownloadStatus(StrEnum):
    """Lifecycle states for a download task."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_REVIEW = "needs_review"


@dataclass(slots=True)
class DownloadTask:
    """Universal task for file acquisition via download providers."""

    task_type: str
    source_id: str
    provider_id: str
    target_folder: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    result_local_file_id: int | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
