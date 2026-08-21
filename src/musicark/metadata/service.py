"""v0.13 multi-format facade over the validated transactional editor service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from musicark.audio.formats import capabilities_for_path
from musicark.audio.probe import probe_audio

from ._service_v012 import MetadataEditorError, MetadataEditorService as _V012MetadataEditorService
from .formats.registry import MetadataAdapterRegistry
from .formats.routing import RoutingMetadataAdapter
from .multiformat_artwork import MultiFormatArtworkCache


class MetadataEditorService(_V012MetadataEditorService):
    """Keep one explicit filesystem transaction while routing format adapters."""

    def __init__(self, base_dir: Path | None = None, *, database_path: Path | None = None) -> None:
        super().__init__(base_dir=base_dir, database_path=database_path)
        self._format_registry = MetadataAdapterRegistry()
        self._adapter = RoutingMetadataAdapter(self._format_registry)
        self._artwork = MultiFormatArtworkCache(self._database_path, base_dir)

    def get(self, local_file_id: int) -> dict[str, Any]:
        row = self._row(local_file_id)
        path = Path(str(row["path"]))
        if not path.is_file():
            raise MetadataEditorError(f"Indexed file is missing on disk: {path}")
        capability = capabilities_for_path(path)
        adapter = self._format_registry.adapter_for(path)
        writable = bool(capability and capability.can_write_metadata and adapter is not None)
        if adapter is not None:
            parsed = adapter.read(path)
            fields = dict(parsed.get("fields") or {})
            all_tags = tuple(parsed.get("allTags") or ())
        else:
            fields = {
                "title": row.get("title"),
                "artists": row.get("artists") or [],
                "album": row.get("album"),
                "albumArtists": [row["album_artist"]] if row.get("album_artist") else [],
                "trackNumber": row.get("track_number"),
                "discNumber": row.get("disc_number"),
                "year": row.get("year"),
                "genres": [row["genre"]] if row.get("genre") else [],
            }
            all_tags = ()
        art = self._artwork.ensure_local(
            int(row["id"]),
            path,
            source_external_id=(str(row["source_external_id"]) if row.get("source_external_id") else None),
        )
        try:
            technical = probe_audio(path).to_dict()
        except Exception:  # noqa: BLE001 - indexed fallback remains available for damaged optional details
            technical = {
                "format": capability.format if capability else path.suffix.lstrip(".").casefold(),
                "container": capability.display_name if capability else path.suffix.lstrip(".").upper(),
                "codec": row.get("codec"),
                "durationSeconds": row.get("duration_seconds"),
                "bitrate": row.get("bitrate"),
                "sampleRate": row.get("sample_rate"),
                "channels": None,
                "bitDepth": None,
            }
        technical.update({"fileSize": row.get("file_size"), "sha256": row.get("sha256")})
        document = {
            "localFileId": int(row["id"]),
            "path": str(path),
            "fileName": path.name,
            "format": capability.display_name if capability else path.suffix.lstrip(".").upper(),
            "writable": writable,
            "fields": fields,
            "allTags": list(all_tags),
            "artwork": art.as_dict(),
            "identity": self._identity_payload(row),
            "technical": technical,
            "formatCapabilities": (
                capability.to_dict()
                if capability is not None
                else {
                    "format": path.suffix.lstrip(".").casefold(),
                    "displayName": path.suffix.lstrip(".").upper(),
                    "canReadMetadata": False,
                    "canWriteMetadata": False,
                    "canReadArtwork": False,
                    "canWriteArtwork": False,
                    "canUploadDirectly": False,
                    "canTranscodeForYandex": False,
                    "metadataMode": "read_only",
                }
            ),
        }
        return {"metadata": document}

    def update(
        self,
        local_file_id: int,
        changes: dict[str, Any],
        *,
        confirm: bool,
        provenance: dict[str, str | None] | None = None,
        artwork_data: bytes | None = None,
        artwork_mime: str | None = None,
    ) -> dict[str, Any]:
        row = self._row(local_file_id)
        path = Path(str(row["path"])).resolve(strict=False)
        capability = capabilities_for_path(path)
        if capability is None or not capability.can_write_metadata:
            raise MetadataEditorError(
                f"Metadata editing is read-only for {path.suffix.casefold() or 'this format'}."
            )
        if (artwork_data is not None or changes.get("artworkImagePath") or changes.get("removeArtwork")) and not capability.can_write_artwork:
            raise MetadataEditorError(
                f"Artwork editing is unavailable for {capability.display_name}."
            )
        return super().update(
            local_file_id,
            changes,
            confirm=confirm,
            provenance=provenance,
            artwork_data=artwork_data,
            artwork_mime=artwork_mime,
        )


__all__ = ["MetadataEditorError", "MetadataEditorService"]
