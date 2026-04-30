"""Provider architecture package for MusicArk v0.2."""

from .base import MusicProvider
from .models import (
    LocalAudioFile,
    ProviderCapabilities,
    ProviderPlaylist,
    ProviderTrack,
    TrackSource,
)
from .registry import ProviderRegistry, ProviderRegistryError

__all__ = [
    "MusicProvider",
    "LocalAudioFile",
    "ProviderCapabilities",
    "ProviderTrack",
    "ProviderPlaylist",
    "TrackSource",
    "ProviderRegistry",
    "ProviderRegistryError",
]
