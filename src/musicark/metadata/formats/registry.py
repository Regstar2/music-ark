"""Adapter registry bound to the central audio capability model."""

from __future__ import annotations

from pathlib import Path

from musicark.audio.formats import capabilities_for_path

from .base import MetadataFormatAdapter
from .generic import GenericReadOnlyMetadataAdapter
from .mp3 import Mp3MetadataAdapter
from .mp4 import Mp4MetadataAdapter
from .vorbis import VorbisMetadataAdapter


class MetadataAdapterRegistry:
    """Resolve one normalized metadata adapter without leaking format tags upward."""

    def __init__(self) -> None:
        self._adapters: tuple[MetadataFormatAdapter, ...] = (
            Mp3MetadataAdapter(),
            VorbisMetadataAdapter(".flac"),
            Mp4MetadataAdapter(),
            VorbisMetadataAdapter(".ogg"),
            VorbisMetadataAdapter(".opus"),
            GenericReadOnlyMetadataAdapter(frozenset({".aac", ".wav"})),
        )

    def adapter_for(self, path: Path) -> MetadataFormatAdapter | None:
        capability = capabilities_for_path(path)
        if capability is None or not capability.can_read_metadata:
            return None
        return next((adapter for adapter in self._adapters if adapter.supports(path)), None)

    def writable_adapter_for(self, path: Path) -> MetadataFormatAdapter | None:
        capability = capabilities_for_path(path)
        if capability is None or not capability.can_write_metadata:
            return None
        return self.adapter_for(path)


DEFAULT_METADATA_ADAPTERS = MetadataAdapterRegistry()
