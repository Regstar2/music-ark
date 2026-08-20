"""Recovery classification for Yandex provider availability and censored/original pairs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ProviderAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class RecoveryState(StrEnum):
    HEALTHY = "healthy"
    UNAVAILABLE_LOCAL_AVAILABLE = "unavailable_local_available"
    UNAVAILABLE_LOCAL_MISSING = "unavailable_local_missing"
    CENSORED_ORIGINAL_AVAILABLE = "censored_original_available"
    CENSORED_ORIGINAL_MISSING = "censored_original_missing"
    UNAVAILABLE_NEEDS_REVIEW = "unavailable_needs_review"
    CENSORSHIP_NEEDS_REVIEW = "censorship_needs_review"


@dataclass(slots=True, frozen=True)
class RecoveryTrack:
    external_id: str
    title: str
    artists: tuple[str, ...]
    album: str | None
    artwork_url: str | None
    collections: tuple[dict[str, Any], ...]
    provider_availability: ProviderAvailability
    local_file_id: int | None
    local_file_name: str | None
    local_extension: str | None
    provider_content_label: str | None
    local_content_label: str | None
    variant_status: str
    state: RecoveryState

    @property
    def local_mp3_ready(self) -> bool:
        return self.local_file_id is not None and self.local_extension == ".mp3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "externalId": self.external_id,
            "title": self.title,
            "artists": list(self.artists),
            "album": self.album,
            "artworkUrl": self.artwork_url,
            "collections": [dict(value) for value in self.collections],
            "providerAvailability": self.provider_availability.value,
            "localFileId": self.local_file_id,
            "localFileName": self.local_file_name,
            "localExtension": self.local_extension,
            "providerContentLabel": self.provider_content_label,
            "localContentLabel": self.local_content_label,
            "variantStatus": self.variant_status,
            "recoveryState": self.state.value,
            "localMp3Ready": self.local_mp3_ready,
        }
