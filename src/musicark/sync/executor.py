"""Sync executor scaffolding (v0.11 experimental upload).

Dangerous planner operations must still pass through explicit confirmations in UI CLI.
Concrete upload execution is delegated to providers until a stable API exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.providers.yandex_experimental_upload import run_experimental_yandex_upload


def execute_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Thin wrapper preserved for symmetry with sync-executor roadmap."""
    return run_experimental_yandex_upload(database_path=database_path, base_dir=base_dir, payload=payload)
