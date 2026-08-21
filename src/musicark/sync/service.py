"""v0.13 format-aware facade over the existing Controlled Sync executor."""

from __future__ import annotations

from typing import Any

from musicark.audio.formats import capabilities_for_extension

from ._service_v0111 import SyncService as _V0111SyncService, SyncServiceError


class _UploadCapableLocalRepository:
    """Relax only the legacy MP3 revalidation gate for safely convertible files."""

    def __init__(self, underlying: Any) -> None:
        self._underlying = underlying

    def __getattr__(self, name: str) -> Any:
        return getattr(self._underlying, name)

    def get_track(self, track_id: int) -> dict[str, Any] | None:
        row = self._underlying.get_track(track_id)
        if row is None:
            return None
        item = dict(row)
        capability = capabilities_for_extension(str(item.get("extension") or ""))
        if capability is not None and (
            capability.can_upload_directly or capability.can_transcode_for_yandex
        ):
            # The legacy executor checks only extension here. Batch/single-track
            # services resolve the authoritative DB row again before conversion.
            item["extension"] = ".mp3"
        return item


class SyncService(_V0111SyncService):
    """Preserve revalidation/rights/idempotency while allowing conversion-required upload."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._local = _UploadCapableLocalRepository(self._local)


__all__ = ["SyncService", "SyncServiceError"]
