"""Sync execution entry points.

Production v0.8 execution is owned by :class:`musicark.sync.service.SyncService`.
The old experimental Yandex upload probe is kept as an explicitly separate
compatibility helper and is never generated or invoked by Controlled Sync.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.providers.yandex_experimental_upload import run_experimental_yandex_upload

from .safe_execution import SyncSafeExecutor, resolve_latest_plan_id
from .service import SyncService, SyncServiceError


def execute_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Explicit legacy/experimental probe; not part of v0.8 Sync Apply."""
    return run_experimental_yandex_upload(
        database_path=database_path, base_dir=base_dir, payload=payload
    )


__all__ = [
    "SyncSafeExecutor",
    "SyncService",
    "SyncServiceError",
    "execute_experimental_yandex_upload",
    "resolve_latest_plan_id",
]
