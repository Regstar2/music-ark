"""Base protocol for provider adapters in MusicArk."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ProviderCapabilities, ProviderPlaylist, ProviderTrack


class MusicProvider(ABC):
    """Contract for music-service provider adapters.

    Providers expose capabilities and data snapshots. They do not implement
    download backend logic and must stay separate from download providers.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Return stable provider identifier, e.g. 'yandex_music'."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return human-readable provider name."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return declared provider capabilities."""

    @abstractmethod
    def health_check(self) -> dict[str, str]:
        """Return provider adapter health without calling remote APIs."""

    @abstractmethod
    def list_tracks(self) -> list[ProviderTrack]:
        """Return provider tracks snapshot.

        TODO(v0.3-yandex-scan): implement real provider scanning.
        """

    @abstractmethod
    def list_playlists(self) -> list[ProviderPlaylist]:
        """Return provider playlists snapshot.

        TODO(v0.3-yandex-scan): implement real provider scanning.
        """
