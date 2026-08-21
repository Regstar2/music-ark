"""Path-aware adapter preserving the existing transactional editor boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import MetadataFormatAdapter, MetadataFormatError
from .registry import MetadataAdapterRegistry


class RoutingMetadataAdapter(MetadataFormatAdapter):
    """Delegate explicit reads/writes to the validated container adapter."""

    extensions = frozenset({".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".opus"})

    def __init__(self, registry: MetadataAdapterRegistry | None = None) -> None:
        self._registry = registry or MetadataAdapterRegistry()

    def _readable(self, path: Path) -> MetadataFormatAdapter:
        adapter = self._registry.adapter_for(path)
        if adapter is None:
            raise MetadataFormatError(f"Metadata reading is not supported for {path.suffix.casefold()}.")
        return adapter

    def _writable(self, path: Path) -> MetadataFormatAdapter:
        adapter = self._registry.writable_adapter_for(path)
        if adapter is None:
            raise MetadataFormatError(f"Metadata writing is not supported for {path.suffix.casefold()}.")
        return adapter

    def supports(self, path: Path) -> bool:
        return self._registry.writable_adapter_for(path) is not None

    def read(self, path: Path) -> dict[str, Any]:
        return self._readable(path).read(path)

    def apply(
        self,
        path: Path,
        changes: dict[str, Any],
        *,
        artwork_data: bytes | None = None,
        artwork_mime: str | None = None,
        remove_artwork: bool = False,
        provenance: dict[str, str | None] | None = None,
    ) -> None:
        self._writable(path).apply(
            path,
            changes,
            artwork_data=artwork_data,
            artwork_mime=artwork_mime,
            remove_artwork=remove_artwork,
            provenance=provenance,
        )

    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        return self._readable(path).artwork(path)

    def validate_audio(self, path: Path) -> float | None:
        return self._readable(path).validate_audio(path)
