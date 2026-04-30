"""Provider-facing universal models for MusicArk v0.2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Declares which operations a music provider supports.

    This model is consumed by core/UI planning logic and must stay provider-agnostic.
    """

    can_authenticate: bool
    can_scan_library: bool
    can_scan_playlists: bool
    can_download_tracks: bool
    can_upload_tracks: bool
    can_create_playlists: bool
    can_edit_playlists: bool
    supports_track_availability: bool
    supports_user_uploads: bool


@dataclass(frozen=True, slots=True)
class ProviderTrack:
    """Provider-specific track snapshot mapped into a neutral shape."""

    provider_id: str
    external_id: str
    title: str
    artists: tuple[str, ...]
    album_external_id: str | None = None
    album_title: str | None = None
    duration_seconds: int | None = None
    explicit: bool | None = None
    availability: str | None = None
    source_type: str = "provider"
    raw_payload_ref: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderPlaylist:
    """Provider-specific playlist snapshot mapped into a neutral shape."""

    provider_id: str
    external_id: str
    title: str
    track_external_ids: tuple[str, ...]
    owner_name: str | None = None
    visibility: str | None = None
    source_type: str = "provider"
    raw_payload_ref: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrackSource:
    """Universal source descriptor for links between track and provider origin."""

    track_id: str
    source_type: str
    provider_id: str
    external_id: str
    url: str | None = None
    availability: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
