"""Compatibility wrapper around the v0.8 production SyncService.

Legacy plans are deliberately unsupported. The executor never instantiates the
historical DownloadSystem and never drains the global queue.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.storage.sync_storage import SyncStorageRepository

from .service import SyncService


def resolve_latest_plan_id(database_path: Path) -> str | None:
    return SyncStorageRepository(database_path).latest_plan_id()


class SyncSafeExecutor:
    """Preserve the old entry point while delegating to v0.8 Controlled Sync."""

    def __init__(self, *, database_path: Path, base_dir: Path | None) -> None:
        self._service = SyncService(base_dir=base_dir, database_path=database_path)
        self._database_path = Path(database_path)

    def execute_safe_plan_operations(
        self, *, plan_id: str | None, confirm: bool
    ) -> dict[str, Any]:
        if confirm is not True:
            raise ValueError('Safe sync execution requires {"confirm": true}.')
        pid = plan_id or resolve_latest_plan_id(self._database_path)
        if pid is None:
            raise ValueError("No sync plan exists. Create a v0.8 plan first.")
        return self._service.apply(pid, confirm=True)
