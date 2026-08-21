"""Read-only metadata extraction for local audio files.

This module deliberately exposes no write operation. Scanner/Matching/Coverage
never mutate user audio; explicit writes remain in the Metadata Editor service.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from musicark.audio.probe import probe_audio
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
    # Existing trusted provenance uses ID3 TXXX and therefore remains MP3-only.
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
    """Extract normalized tags, technical properties and trusted origin."""

    def read(self, path: Path) -> LocalTrackMetadata:
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(path), easy=True)
        except Exception as exc:  # noqa: BLE001 - isolated per-file failure.
            raise LocalMetadataError(f"Cannot read metadata: {path}") from exc
        if audio is None:
            raise LocalMetadataError(f"Unsupported or corrupted audio file: {path}")

        tags = getattr(audio, "tags", None)
        title = _first(tags, "title") or path.stem
        artists = _values(tags, "artist") or _values(tags, "artists")
        album = _first(tags, "album")
        album_artist = _first(tags, "albumartist", "album artist")
        track_number = _number(_first(tags, "tracknumber"))
        disc_number = _number(_first(tags, "discnumber"))
        year = _year(_first(tags, "date", "year"))
        genre = _first(tags, "genre")
        source_provider_id, source_external_id = _provenance(path)
        try:
            technical = probe_audio(path)
        except Exception as exc:  # noqa: BLE001
            raise LocalMetadataError(f"Cannot read technical audio information: {path}") from exc

        return LocalTrackMetadata(
            title=title,
            artists=artists,
            album=album,
            album_artist=album_artist,
            track_number=track_number,
            disc_number=disc_number,
            year=year,
            genre=genre,
            duration_seconds=technical.duration_seconds,
            codec=technical.codec,
            container=technical.container,
            bitrate=technical.bitrate,
            sample_rate=technical.sample_rate,
            channels=technical.channels,
            bit_depth=technical.bit_depth,
            source_provider_id=source_provider_id,
            source_external_id=source_external_id,
        )
