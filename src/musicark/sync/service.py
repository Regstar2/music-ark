"""v0.13 format-aware facade over the existing Controlled Sync executor."""

from __future__ import annotations

from typing import Any

from musicark.audio.formats import capabilities_for_extension

from ._service_v0111 import SyncService as _V0111SyncService, SyncServiceError
from .models import SyncOperationStatus, SyncOperationType


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
    """Preserve safe execution while rejecting the retired unavailable upload role."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._local = _UploadCapableLocalRepository(self._local)

    def apply(
        self,
        plan_id: str,
        *,
        confirm: bool,
        rights_confirmed: bool = False,
    ) -> dict[str, Any]:
        # Plans created before #54 may contain targetRole='unavailable'. They are
        # retained for history, but must never execute after that target was
        # retired from the product model.
        plan = self._storage.get_plan(plan_id)
        for operation in plan.operations:
            if (
                operation.operation_type == SyncOperationType.UPLOAD_LOCAL_TO_YANDEX
                and operation.status == SyncOperationStatus.PENDING
                and str(operation.metadata.get("targetRole") or "") == "unavailable"
            ):
                raise SyncServiceError(
                    "This Sync Plan contains the retired unavailable-track upload target. Create a new plan.",
                    code="legacy_plan_unsupported",
                )
        return super().apply(
            plan_id,
            confirm=confirm,
            rights_confirmed=rights_confirmed,
        )


__all__ = ["SyncService", "SyncServiceError"]
