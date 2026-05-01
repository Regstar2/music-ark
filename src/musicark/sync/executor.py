"""Sync executor scaffolding.

v0.11: experimental upload probes via [[yandex-music-provider]] helpers.

v1.0: safe execution of persisted planner ops (``CREATE_DOWNLOAD_TASK`` for Yandex downloads) is in
``musicark.sync.safe_execution``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.providers.yandex_experimental_upload import run_experimental_yandex_upload

from .safe_execution import SyncSafeExecutor, resolve_latest_plan_id


def execute_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Thin wrapper preserved for symmetry with sync-executor roadmap."""
    return run_experimental_yandex_upload(database_path=database_path, base_dir=base_dir, payload=payload)


__all__ = [
    "SyncSafeExecutor",
    "execute_experimental_yandex_upload",
    "resolve_latest_plan_id",
]
