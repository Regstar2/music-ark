"""Download queue domain models for MusicArk v0.8.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from musicark.providers.models import LocalAudioFile


class DownloadStatus(StrEnum):
    """Persisted lifecycle states for a download task."""

    # PENDING/PAUSED are retained only for backwards compatibility with pre-v0.7 rows.
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    NEEDS_REVIEW = "needs_review"


@dataclass(slots=True)
class DownloadTask:
    """Universal persisted task for file acquisition via download providers.

    Credentials and temporary provider URLs must never be stored in this object.
    ``target_folder`` is a snapshot of the destination chosen at enqueue time.
    """

    task_type: str
    source_id: str
    provider_id: str
    target_folder: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    cancel_requested: bool = False
    target_root_id: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_local_file_id: int | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    """Enriched output returned by providers that finalize metadata before indexing.

    ``provider_raw_metadata`` is public provider metadata only. Credentials and
    temporary signed download URLs must never cross this boundary.
    """

    audio: LocalAudioFile
    metadata_snapshot: dict[str, Any] = field(default_factory=dict)
    provider_raw_metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
