"""Provider architecture package for MusicArk v0.2."""

from .base import MusicProvider
from .local_library_provider import LocalLibraryProviderStub
from .models import ProviderCapabilities, ProviderPlaylist, ProviderTrack, TrackSource
from .registry import ProviderRegistry, ProviderRegistryError
from .yandex_music_provider import YandexMusicProviderStub

__all__ = [
    "MusicProvider",
    "ProviderCapabilities",
    "ProviderTrack",
    "ProviderPlaylist",
    "TrackSource",
    "ProviderRegistry",
    "ProviderRegistryError",
    "YandexMusicProviderStub",
    "LocalLibraryProviderStub",
]
