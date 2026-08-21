"""Format-aware recovery classification over the v0.11.1 recovery service."""

from __future__ import annotations

from typing import Any

from musicark.audio.formats import capabilities_for_extension

from ._service_v0111 import RecoveryService as _V0111RecoveryService
from .models import ProviderAvailability, RecoveryState


class RecoveryService(_V0111RecoveryService):
    """Treat direct and safely convertible local audio as recoverable candidates."""

    @staticmethod
    def _state(
        availability: ProviderAvailability,
        context: dict[str, Any],
    ) -> RecoveryState:
        extension = str(context.get("localExtension") or "").casefold()
        capability = capabilities_for_extension(extension)
        uploadable = bool(
            capability
            and (capability.can_upload_directly or capability.can_transcode_for_yandex)
        )
        # Reuse the validated recovery state machine by changing only its legacy
        # MP3 admission predicate. The real extension remains in RecoveryTrack and
        # is therefore still available to planner/UI classification.
        if uploadable and extension != ".mp3":
            compatible = dict(context)
            compatible["localExtension"] = ".mp3"
            return _V0111RecoveryService._state(availability, compatible)
        return _V0111RecoveryService._state(availability, context)


__all__ = ["RecoveryService"]
