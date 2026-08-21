"""Format-aware read-only Controlled Sync planner facade."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from musicark.audio.formats import capabilities_for_extension
from musicark.recovery.models import RecoveryTrack

from ._planner_v0111 import (
    DOWNLOAD_PROVIDER,
    PLANNER_VERSION,
    SOURCE_PROVIDER,
    SyncPlanner as _V0111SyncPlanner,
    SyncPlannerError,
    _PlanInput,
)
from .models import SyncOperation


class SyncPlanner(_V0111SyncPlanner):
    """Add format intent to recovery plans without invoking FFmpeg during planning."""

    def _recovery_operation(
        self,
        data: _PlanInput,
        recovery: RecoveryTrack,
        metadata: dict[str, Any],
    ) -> SyncOperation | None:
        operation = super()._recovery_operation(data, recovery, metadata)
        if operation is None:
            return None
        capability = capabilities_for_extension(str(recovery.local_extension or ""))
        if capability is None or not (
            capability.can_upload_directly or capability.can_transcode_for_yandex
        ):
            return None
        conversion_required = bool(
            not capability.can_upload_directly and capability.can_transcode_for_yandex
        )
        reason = operation.reason
        if reason == "provider_unavailable_local_mp3":
            reason = (
                "provider_unavailable_local_conversion_required"
                if conversion_required
                else "provider_unavailable_local_direct_upload"
            )
        return replace(
            operation,
            reason=reason,
            metadata={
                **operation.metadata,
                "sourceFormat": capability.format,
                "uploadMode": "convert" if conversion_required else "direct",
                "conversionRequired": conversion_required,
            },
        )


__all__ = [
    "DOWNLOAD_PROVIDER",
    "PLANNER_VERSION",
    "SOURCE_PROVIDER",
    "SyncPlanner",
    "SyncPlannerError",
    "_PlanInput",
]
