"""Normalized Mutagen reader used by conservative read-only formats."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .base import MetadataFormatAdapter, MetadataFormatError

_YEAR_RE = re.compile(r"(18|19|20|21)\d{2}")


def text_values(tags: Any, key: str) -> list[str]:
    if tags is None:
        return []
    try:
        value = tags.get(key)
    except AttributeError:
        return []
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def first(tags: Any, *keys: str) -> str | None:
    for key in keys:
        values = text_values(tags, key)
        if values:
            return values[0]
    return None


def split_number(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    left, _, right = value.partition("/")
    try:
        current = int(left.strip()) if left.strip() else None
    except ValueError:
        current = None
    try:
        total = int(right.strip()) if right.strip() else None
    except ValueError:
        total = None
    return current, total


def normalized_easy_fields(path: Path) -> dict[str, Any]:
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(str(path), easy=True)
    except Exception as exc:  # noqa: BLE001
        raise MetadataFormatError(f"Cannot read audio metadata: {path}") from exc
    if audio is None:
        raise MetadataFormatError(f"Unsupported or corrupted audio file: {path}")
    tags = getattr(audio, "tags", None)
    track, track_total = split_number(first(tags, "tracknumber"))
    disc, disc_total = split_number(first(tags, "discnumber"))
    release_date = first(tags, "date", "year")
    year = None
    if release_date:
        match = _YEAR_RE.search(release_date)
        year = int(match.group(0)) if match else None
    return {
        "title": first(tags, "title"),
        "artists": text_values(tags, "artist") or text_values(tags, "artists"),
        "album": first(tags, "album"),
        "albumArtists": text_values(tags, "albumartist",) or text_values(tags, "album artist"),
        "trackNumber": track,
        "totalTracks": track_total,
        "discNumber": disc,
        "totalDiscs": disc_total,
        "releaseDate": release_date,
        "year": year,
        "genres": text_values(tags, "genre"),
        "composer": first(tags, "composer"),
        "comment": first(tags, "comment", "description"),
        "lyrics": first(tags, "lyrics", "unsyncedlyrics"),
    }


def validate_generic_audio(path: Path) -> float | None:
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(str(path))
        info = getattr(audio, "info", None) if audio is not None else None
        if info is None:
            raise MetadataFormatError("Audio stream information is missing.")
        raw = getattr(info, "length", None)
        return float(raw) if raw is not None else None
    except MetadataFormatError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MetadataFormatError(f"Audio validation failed: {path}") from exc


class GenericReadOnlyMetadataAdapter(MetadataFormatAdapter):
    """Read normalized tags but reject every explicit write fail-closed."""

    def __init__(self, extensions: frozenset[str]) -> None:
        self.extensions = extensions

    def read(self, path: Path) -> dict[str, Any]:
        return {"fields": normalized_easy_fields(path), "allTags": []}

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
        raise MetadataFormatError(f"Metadata writing is not supported for {path.suffix.casefold()}.")

    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        return None

    def validate_audio(self, path: Path) -> float | None:
        return validate_generic_audio(path)
