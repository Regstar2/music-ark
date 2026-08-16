"""Value objects used by the v0.4 local library scanner."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class LocalLibraryRoot:
    id: int
    path: str
    normalized_path: str
    enabled: bool
    created_at: str
    last_scanned_at: str | None = None


@dataclass(frozen=True, slots=True)
class LocalTrackMetadata:
    title: str
    artists: tuple[str, ...] = ()
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None
    duration_seconds: float | None = None
    codec: str = ""
    bitrate: int | None = None
    sample_rate: int | None = None
    source_provider_id: str | None = None
    source_external_id: str | None = None


@dataclass(frozen=True, slots=True)
class LocalAudioRecord:
    library_root_id: int
    path: str
    normalized_path: str
    file_name: str
    extension: str
    file_size: int
    modified_ns: int
    metadata: LocalTrackMetadata
    sha256: str = ""


@dataclass(slots=True)
class LocalScanResult:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    errors: int = 0
    scanned_files: int = 0
    error_items: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "scanned": self.scanned_files,
            "errorItems": self.error_items,
        }
