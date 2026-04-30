"""Local library provider stub for architecture validation."""

from __future__ import annotations

from .base import MusicProvider
from .models import ProviderCapabilities, ProviderPlaylist, ProviderTrack


class LocalLibraryProviderStub(MusicProvider):
    """Local library provider stub without filesystem scanning.

    TODO(v0.4-local-library): implement real local archive scanning.
    """

    @property
    def provider_id(self) -> str:
        return "local_library"

    @property
    def display_name(self) -> str:
        return "Local Library (stub)"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_authenticate=False,
            can_scan_library=False,
            can_scan_playlists=False,
            can_download_tracks=False,
            can_upload_tracks=True,
            can_create_playlists=False,
            can_edit_playlists=False,
            supports_track_availability=True,
            supports_user_uploads=True,
        )

    def health_check(self) -> dict[str, str]:
        return {"status": "ok", "mode": "stub"}

    def list_tracks(self) -> list[ProviderTrack]:
        return []

    def list_playlists(self) -> list[ProviderPlaylist]:
        return []
