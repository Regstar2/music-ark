"""MusicArk Controlled Sync application layer.

Only the lightweight domain models are imported eagerly. Planner and service are
loaded lazily to keep storage/model imports acyclic: sync storage depends on the
models, while the planner/service depend on storage repositories.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
    SyncPlan,
    SyncPlanStatus,
    SyncScopeType,
)

if TYPE_CHECKING:
    from .planner import PLANNER_VERSION, SyncPlanner, SyncPlannerError
    from .service import SyncService, SyncServiceError


_PLANNER_EXPORTS = {"PLANNER_VERSION", "SyncPlanner", "SyncPlannerError"}
_SERVICE_EXPORTS = {"SyncService", "SyncServiceError"}


def __getattr__(name: str) -> Any:
    """Load orchestration exports on demand without creating package cycles."""
    if name in _PLANNER_EXPORTS:
        module = import_module(".planner", __name__)
        return getattr(module, name)
    if name in _SERVICE_EXPORTS:
        module = import_module(".service", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PLANNER_VERSION",
    "SyncOperation",
    "SyncOperationStatus",
    "SyncOperationType",
    "SyncPlan",
    "SyncPlanStatus",
    "SyncPlanner",
    "SyncPlannerError",
    "SyncScopeType",
    "SyncService",
    "SyncServiceError",
]
