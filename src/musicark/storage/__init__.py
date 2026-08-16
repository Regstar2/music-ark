"""MusicArk storage package.

Sync storage is loaded lazily because it depends on ``musicark.sync.models``.
Keeping that cross-package edge out of package initialization prevents unrelated
storage imports (for example ``audit_log``) from initializing the Sync planner.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .audit_log import AuditEvent, AuditLogRepository
from .database import initialize_database
from .download_storage import DownloadStorageRepository
from .local_library_storage import LocalLibraryStorageRepository
from .matching_storage import MatchingStorageRepository
from .provider_storage import ProviderStorageRepository

if TYPE_CHECKING:
    from .sync_storage import SyncStorageRepository


def __getattr__(name: str) -> Any:
    if name == "SyncStorageRepository":
        module = import_module(".sync_storage", __name__)
        return module.SyncStorageRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "initialize_database",
    "AuditEvent",
    "AuditLogRepository",
    "ProviderStorageRepository",
    "LocalLibraryStorageRepository",
    "DownloadStorageRepository",
    "MatchingStorageRepository",
    "SyncStorageRepository",
]
