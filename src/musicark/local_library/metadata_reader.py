"""Read-only metadata extraction for local audio files.

This module deliberately exposes no write operation. MusicArk never mutates
user audio while scanning; v0.8.1 only recognizes provenance already embedded
in files created by the download pipeline.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from musicark.core.errors import MusicArkError
from musicark.provenance import trusted_yandex_origin
from .models import LocalTrackMetadata


class LocalMetadataError(MusicArkError):
    """Raised when one local file cannot be parsed as audio."""


_YEAR_RE = re.compile(r"(18|19|20|21)\d{2}")


def _values(tags: Any, key: str) -> tuple[str, ...]:
    if not tags:
        return ()
    try:
        raw = tags.get(key)
    except AttributeError:
        return ()
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        values = tuple(str(item).strip() for item in raw if str(item).strip())
    else:
        value = str(raw).strip()
        values = (value,) if value else ()
    return values


def _first(tags: Any, *keys: str) -> str | None:
    for key in keys:
        values = _values(tags, key)
        if values:
            return values[0]
    return None


def _number(raw: str | None) -> int | None:
    if not raw:
        return None
    head = raw.split("/", 1)[0].strip()
    try:
        return int(head)
    except (TypeError, ValueError):
        return None


def _year(raw: str | None) -> int | None:
    if not raw:
        return None
    match = _YEAR_RE.search(raw)
    return int(match.group(0)) if match else None


def _provenance(path: Path) -> tuple[str | None, str | None]:
    if path.suffix.casefold() != ".mp3":
        return None, None
    try:
        from mutagen.id3 import ID3

        tags = ID3(str(path))
    except Exception:  # noqa: BLE001 - provenance is optional for normal user files.
        return None, None
    values: dict[str, str] = {}
    for frame in tags.getall("TXXX"):
        description = str(getattr(frame, "desc", ""))
        text = getattr(frame, "text", ())
        if description and text:
            values[description] = str(text[0]).strip()
    return trusted_yandex_origin(values)


class LocalMetadataReader:
    """Extract matching-relevant tags, technical properties, and trusted origin."""

    def read(self, path: Path) -> LocalTrackMetadata:
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(path), easy=True)
        except Exception as exc:  # noqa: BLE001 - isolated per-file failure.
            raise LocalMetadataError(f"Cannot read metadata: {path}") from exc
        if audio is None:
            raise LocalMetadataError(f"Unsupported or corrupted audio file: {path}")

        tags = getattr(audio, "tags", None)
        info = getattr(audio, "info", None)
        title = _first(tags, "title") or path.stem
        artists = _values(tags, "artist") or _values(tags, "artists")
        album = _first(tags, "album")
        album_artist = _first(tags, "albumartist", "album artist")
        track_number = _number(_first(tags, "tracknumber"))
        disc_number = _number(_first(tags, "discnumber"))
        year = _year(_first(tags, "date", "year"))
        genre = _first(tags, "genre")
        source_provider_id, source_external_id = _provenance(path)

        duration = None
        bitrate = None
        sample_rate = None
        if info is not None:
            raw_duration = getattr(info, "length", None)
            if raw_duration:
                try:
                    duration = float(raw_duration)
                except (TypeError, ValueError):
                    duration = None
            raw_bitrate = getattr(info, "bitrate", None)
            if raw_bitrate:
                try:
                    bitrate = int(raw_bitrate)
                except (TypeError, ValueError):
                    bitrate = None
            raw_sample_rate = getattr(info, "sample_rate", None)
            if raw_sample_rate:
                try:
                    sample_rate = int(raw_sample_rate)
                except (TypeError, ValueError):
                    sample_rate = None

        return LocalTrackMetadata(
            title=title,
            artists=artists,
            album=album,
            album_artist=album_artist,
            track_number=track_number,
            disc_number=disc_number,
            year=year,
            genre=genre,
            duration_seconds=duration,
            codec=path.suffix.lower().lstrip("."),
            bitrate=bitrate,
            sample_rate=sample_rate,
            source_provider_id=source_provider_id,
            source_external_id=source_external_id,
        )
