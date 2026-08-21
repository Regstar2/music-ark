"""Multi-format embedded-artwork support over the existing cache lifecycle."""

from __future__ import annotations

from pathlib import Path

from musicark.audio.formats import capabilities_for_path

from .artwork import ArtworkCache
from .formats.registry import MetadataAdapterRegistry
from .models import ArtworkInfo


class MultiFormatArtworkCache(ArtworkCache):
    """Reuse the v0.8.2 cache while reading embedded artwork by capability."""

    def __init__(self, database_path: Path, base_dir: Path | None) -> None:
        super().__init__(database_path, base_dir)
        self._registry = MetadataAdapterRegistry()

    def ensure_local(
        self,
        local_file_id: int,
        path: Path,
        *,
        source_external_id: str | None = None,
    ) -> ArtworkInfo:
        fingerprint = self._fingerprint(path)
        cached = self._cached(local_file_id, fingerprint)
        if cached is not None:
            return cached

        capability = capabilities_for_path(path)
        embedded: tuple[bytes, str] | None = None
        if capability is not None and capability.can_read_artwork:
            adapter = self._registry.adapter_for(path)
            if adapter is not None:
                try:
                    embedded = adapter.artwork(path)
                except Exception:  # noqa: BLE001 - artwork is optional for a normal library row
                    embedded = None
        if embedded is not None:
            return self._store_local(
                local_file_id,
                fingerprint,
                embedded[0],
                embedded[1],
                source="embedded",
            )

        if source_external_id:
            yandex_path = self.yandex_cached(source_external_id)
            if yandex_path:
                data = Path(yandex_path).read_bytes()
                mime = "image/png" if yandex_path.casefold().endswith(".png") else "image/jpeg"
                return self._store_local(
                    local_file_id,
                    fingerprint,
                    data,
                    mime,
                    source="yandex_identity_cache",
                )

        self._clear_local(local_file_id)
        return ArtworkInfo()
