"""Provider-neutral metadata editor models for explicit local-file edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BASIC_FIELDS = (
    "title", "subtitle", "version", "artists", "album", "albumArtists",
    "trackNumber", "totalTracks", "discNumber", "totalDiscs", "releaseDate",
    "year", "genres", "isrc", "publisher", "label", "copyright", "composer",
    "lyricist", "bpm", "comment", "grouping", "lyrics", "explicit", "artwork",
)


@dataclass(frozen=True, slots=True)
class ArtworkInfo:
    """Small UI-safe artwork descriptor; binary artwork never crosses the bridge."""

    present: bool = False
    cache_path: str | None = None
    mime: str | None = None
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "cachePath": self.cache_path,
            "mime": self.mime,
            "width": self.width,
            "height": self.height,
            "byteSize": self.byte_size,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class MetadataDocument:
    """Complete editable metadata snapshot independent of a concrete tag format."""

    local_file_id: int
    path: str
    format: str
    writable: bool
    fields: dict[str, Any] = field(default_factory=dict)
    all_tags: tuple[dict[str, Any], ...] = ()
    artwork: ArtworkInfo = ArtworkInfo()
    identity: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "localFileId": self.local_file_id,
            "path": self.path,
            "format": self.format,
            "writable": self.writable,
            "fields": self.fields,
            "allTags": list(self.all_tags),
            "artwork": self.artwork.as_dict(),
            "identity": self.identity,
        }


def nonempty(value: Any) -> bool:
    """True when a provider field carries actual information worth importing."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True
