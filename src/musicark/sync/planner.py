"""Format-aware read-only Controlled Sync planner facade."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from musicark.audio.formats import capabilities_for_extension
from musicark.recovery.models import RecoveryState, RecoveryTrack

from ._planner_v0111 import (
    DOWNLOAD_PROVIDER,
    PLANNER_VERSION,
    SOURCE_PROVIDER,
    SyncPlanner as _V0111SyncPlanner,
    SyncPlannerError,
    _PlanInput,
)
from .models import SyncOperation, SyncPlan


_ACTIVE_MANAGED_ROLES = frozenset({"censored", "uploaded"})


class SyncPlanner(_V0111SyncPlanner):
    """Add format intent while keeping unavailable provider tracks diagnostic-only."""

    def _read_inputs(self, **kwargs: Any) -> _PlanInput:
        data = super()._read_inputs(**kwargs)
        # Legacy databases may still contain role='unavailable'. Keep the row on
        # disk for backward compatibility, but never let it affect a new plan or
        # its fingerprint.
        managed = {
            role: item
            for role, item in data.managed.items()
            if role in _ACTIVE_MANAGED_ROLES
        }
        return replace(data, managed=managed)

    def _recovery_operation(
        self,
        data: _PlanInput,
        recovery: RecoveryTrack,
        metadata: dict[str, Any],
    ) -> SyncOperation | None:
        # An unavailable Yandex source identity cannot be restored through a
        # managed playlist. Local availability remains visible in Recovery, but
        # Sync must not turn it into an upload destination.
        if recovery.state == RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE:
            return None

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
        return replace(
            operation,
            metadata={
                **operation.metadata,
                "sourceFormat": capability.format,
                "uploadMode": "convert" if conversion_required else "direct",
                "conversionRequired": conversion_required,
            },
        )

    def _plan_from_inputs(self, data: _PlanInput, *, dry_run: bool) -> SyncPlan:
        plan = super()._plan_from_inputs(data, dry_run=dry_run)
        summary = dict(plan.summary)

        # The legacy planner counts a locally available unavailable track as a
        # blocked upload when _recovery_operation returns None. In v1.0 this is
        # informational, not a blocker or an upload candidate.
        informational_unavailable = int(summary.get("unavailableRecoverable", 0) or 0)
        summary["uploadBlocked"] = max(
            0,
            int(summary.get("uploadBlocked", 0) or 0) - informational_unavailable,
        )
        summary["blockerCount"] = max(
            0,
            int(summary.get("blockerCount", 0) or 0) - informational_unavailable,
        )
        upload_by_role = summary.get("uploadByRole")
        censored = (
            int(upload_by_role.get("censored", 0) or 0)
            if isinstance(upload_by_role, dict)
            else 0
        )
        summary["uploadByRole"] = {"censored": censored}
        return replace(plan, summary=summary)


__all__ = [
    "DOWNLOAD_PROVIDER",
    "PLANNER_VERSION",
    "SOURCE_PROVIDER",
    "SyncPlanner",
    "SyncPlannerError",
    "_PlanInput",
]
