"""Application service for v0.11.1 recovery classification and summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.recovery_storage import RecoveryStorageRepository

from .models import ProviderAvailability, RecoveryState, RecoveryTrack

_VARIANT_REVIEW = frozenset({"altered", "different_version", "uncertain"})


class RecoveryService:
    """Derive recovery state without conflating provider availability with local Coverage."""

    def __init__(
        self,
        database_path: Path,
        *,
        repository: RecoveryStorageRepository | None = None,
        audit_repository: AuditLogRepository | None = None,
    ) -> None:
        self._database_path = Path(database_path)
        self._repository = repository or RecoveryStorageRepository(self._database_path)
        self._audit = audit_repository or AuditLogRepository(self._database_path)

    @staticmethod
    def _availability(signals: Iterable[str]) -> ProviderAvailability:
        values = [str(value).strip().casefold() for value in signals]
        # An explicit available=false snapshot is a strong provider signal.  Mixed
        # playlist snapshots therefore remain unavailable until a later refresh
        # explicitly proves availability again.
        if "unavailable" in values:
            return ProviderAvailability.UNAVAILABLE
        if values and all(value == "available" for value in values):
            return ProviderAvailability.AVAILABLE
        return ProviderAvailability.UNKNOWN

    @staticmethod
    def _state(
        availability: ProviderAvailability,
        context: dict[str, Any],
    ) -> RecoveryState:
        local_file_id = context.get("localFileId") if context.get("matchingStatus") == "matched" else None
        local_available = bool(context.get("localAvailable")) and local_file_id is not None
        local_extension = str(context.get("localExtension") or "").casefold()
        provider_label = str(context.get("providerContentLabel") or "").casefold()
        local_label = str(context.get("localContentLabel") or "").casefold()
        variant = str(context.get("variantStatus") or "not_checked").casefold()

        if availability == ProviderAvailability.UNAVAILABLE:
            if local_available and local_extension == ".mp3":
                return RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE
            return RecoveryState.UNAVAILABLE_LOCAL_MISSING

        if provider_label == "censored":
            if local_available and local_label == "original" and local_extension == ".mp3":
                return RecoveryState.CENSORED_ORIGINAL_AVAILABLE
            if local_file_id is None or not local_available:
                return RecoveryState.CENSORED_ORIGINAL_MISSING
            return RecoveryState.CENSORSHIP_NEEDS_REVIEW

        # Audio-variant analysis alone is never promoted to a censorship claim.
        if variant in _VARIANT_REVIEW:
            return RecoveryState.CENSORSHIP_NEEDS_REVIEW
        if availability == ProviderAvailability.UNKNOWN:
            return RecoveryState.UNAVAILABLE_NEEDS_REVIEW
        return RecoveryState.HEALTHY

    def _audit_transition(self, external_id: str, previous: str | None, current: str) -> None:
        event_type: str | None = None
        if current == "unavailable" and previous != "unavailable":
            event_type = "provider_track_became_unavailable"
        elif previous == "unavailable" and current == "available":
            event_type = "provider_track_available_again"
        if event_type is None:
            return
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="provider_track",
                entity_id=f"yandex_music:{external_id}",
                status="success",
                details=json.dumps(
                    {"provider": "yandex_music", "externalTrackId": external_id},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        )

    def tracks(self, *, include_healthy: bool = False) -> list[RecoveryTrack]:
        current = self._repository.cached_playlist_memberships()
        history = self._repository.availability_history()
        matching = self._repository.matching_context(current.keys())
        result: list[RecoveryTrack] = []

        for external_id, item in current.items():
            availability = self._availability(item.get("availabilitySignals", []))
            previous, persisted = self._repository.upsert_availability(
                external_id=external_id,
                availability=availability.value,
                title=str(item.get("title") or ""),
                artists=[str(value) for value in item.get("artists", [])],
                album=str(item.get("album")) if item.get("album") is not None else None,
                artwork_url=str(item.get("artworkUrl")) if item.get("artworkUrl") else None,
                collections=[dict(value) for value in item.get("collections", []) if isinstance(value, dict)],
            )
            self._audit_transition(external_id, previous, persisted)
            context = matching.get(external_id, {})
            state = self._state(availability, context)
            track = RecoveryTrack(
                external_id=external_id,
                title=str(item.get("title") or external_id),
                artists=tuple(str(value) for value in item.get("artists", [])),
                album=str(item.get("album")) if item.get("album") is not None else None,
                artwork_url=str(item.get("artworkUrl")) if item.get("artworkUrl") else None,
                collections=tuple(
                    dict(value) for value in item.get("collections", []) if isinstance(value, dict)
                ),
                provider_availability=availability,
                local_file_id=(
                    int(context["localFileId"])
                    if context.get("matchingStatus") == "matched" and context.get("localFileId") is not None
                    else None
                ),
                local_file_name=(
                    str(context.get("localFileName")) if context.get("localFileName") else None
                ),
                local_extension=(
                    str(context.get("localExtension")) if context.get("localExtension") else None
                ),
                provider_content_label=(
                    str(context.get("providerContentLabel"))
                    if context.get("providerContentLabel")
                    else None
                ),
                local_content_label=(
                    str(context.get("localContentLabel")) if context.get("localContentLabel") else None
                ),
                variant_status=str(context.get("variantStatus") or "not_checked"),
                state=state,
            )
            if include_healthy or track.state != RecoveryState.HEALTHY:
                result.append(track)

        # A playlist diff/disappearance is not evidence that Yandex made a track
        # unavailable.  Preserve last-known metadata but move the active state to
        # unknown/needs-review instead of manufacturing an unavailable record.
        disappeared_ids = set(history) - set(current)
        for external_id in disappeared_ids:
            old = history[external_id]
            previous, _ = self._repository.mark_disappeared(external_id)
            context = matching.get(external_id, {})
            track = RecoveryTrack(
                external_id=external_id,
                title=str(old.get("title") or external_id),
                artists=tuple(str(value) for value in old.get("artists", [])),
                album=str(old.get("album")) if old.get("album") is not None else None,
                artwork_url=str(old.get("artworkUrl")) if old.get("artworkUrl") else None,
                collections=tuple(
                    dict(value) for value in old.get("collections", []) if isinstance(value, dict)
                ),
                provider_availability=ProviderAvailability.UNKNOWN,
                local_file_id=None,
                local_file_name=None,
                local_extension=None,
                provider_content_label=None,
                local_content_label=None,
                variant_status="not_checked",
                state=RecoveryState.UNAVAILABLE_NEEDS_REVIEW,
            )
            # Never emit available-again here: disappearance did not prove it.
            _ = previous
            result.append(track)

        result.sort(key=lambda value: (value.state.value, value.artists, value.title.casefold(), value.external_id))
        return result

    def by_external_ids(self, external_ids: Iterable[str]) -> dict[str, RecoveryTrack]:
        wanted = {str(value).strip() for value in external_ids if str(value).strip()}
        if not wanted:
            return {}
        return {item.external_id: item for item in self.tracks(include_healthy=True) if item.external_id in wanted}

    def summary(self) -> dict[str, int]:
        tracks = self.tracks(include_healthy=False)
        counts = {
            "unavailableTracks": 0,
            "unavailableRecoverable": 0,
            "unavailableMissingLocal": 0,
            "censoredTracks": 0,
            "censoredRecoverable": 0,
            "censoredNeedsReview": 0,
            "needsReview": 0,
        }
        for item in tracks:
            state = item.state
            if state in {
                RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE,
                RecoveryState.UNAVAILABLE_LOCAL_MISSING,
            }:
                counts["unavailableTracks"] += 1
            if state == RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE:
                counts["unavailableRecoverable"] += 1
            elif state == RecoveryState.UNAVAILABLE_LOCAL_MISSING:
                counts["unavailableMissingLocal"] += 1
            elif state == RecoveryState.CENSORED_ORIGINAL_AVAILABLE:
                counts["censoredTracks"] += 1
                counts["censoredRecoverable"] += 1
            elif state == RecoveryState.CENSORED_ORIGINAL_MISSING:
                counts["censoredTracks"] += 1
            elif state == RecoveryState.CENSORSHIP_NEEDS_REVIEW:
                counts["censoredNeedsReview"] += 1
                counts["needsReview"] += 1
            elif state == RecoveryState.UNAVAILABLE_NEEDS_REVIEW:
                counts["needsReview"] += 1
        return counts

    def payload(self, *, filter_name: str = "all", limit: int = 500, offset: int = 0) -> dict[str, Any]:
        items = self.tracks(include_healthy=False)
        name = str(filter_name or "all").strip().casefold()
        if name == "recoverable":
            items = [
                item
                for item in items
                if item.state
                in {
                    RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE,
                    RecoveryState.CENSORED_ORIGINAL_AVAILABLE,
                }
            ]
        elif name == "missing_local":
            items = [
                item
                for item in items
                if item.state
                in {
                    RecoveryState.UNAVAILABLE_LOCAL_MISSING,
                    RecoveryState.CENSORED_ORIGINAL_MISSING,
                }
            ]
        elif name == "needs_review":
            items = [
                item
                for item in items
                if item.state
                in {
                    RecoveryState.UNAVAILABLE_NEEDS_REVIEW,
                    RecoveryState.CENSORSHIP_NEEDS_REVIEW,
                }
            ]
        safe_limit = max(1, min(int(limit), 1000))
        safe_offset = max(0, int(offset))
        return {
            "summary": self.summary(),
            "count": len(items),
            "items": [item.to_dict() for item in items[safe_offset : safe_offset + safe_limit]],
        }
