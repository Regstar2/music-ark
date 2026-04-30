"""Yandex Music provider stub for architecture validation."""

from __future__ import annotations

from .base import MusicProvider
from .models import ProviderCapabilities, ProviderPlaylist, ProviderTrack


class YandexMusicProviderStub(MusicProvider):
    """Provider stub without network calls.

    TODO(v0.3-yandex-scan): replace stub methods with real scan implementation.
    """

    @property
    def provider_id(self) -> str:
        return "yandex_music"

    @property
    def display_name(self) -> str:
        return "Yandex Music (stub)"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_authenticate=True,
            can_scan_library=False,
            can_scan_playlists=False,
            can_download_tracks=False,
            can_upload_tracks=False,
            can_create_playlists=False,
            can_edit_playlists=False,
            supports_track_availability=True,
            supports_user_uploads=False,
        )

    def health_check(self) -> dict[str, str]:
        return {"status": "ok", "mode": "stub"}

    def list_tracks(self) -> list[ProviderTrack]:
        return []

    def list_playlists(self) -> list[ProviderPlaylist]:
        return []
