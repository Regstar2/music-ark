"""Yandex metadata normalization and write-only enrichment for new MusicArk downloads."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from musicark.provenance import (
    MUSICARK_EXTERNAL_ID,
    MUSICARK_METADATA_SCHEMA,
    MUSICARK_METADATA_SCHEMA_VERSION,
    MUSICARK_PROVIDER,
    PROVENANCE_DESCRIPTIONS,
    YANDEX_ALBUM_ID,
    YANDEX_ARTIST_IDS,
    YANDEX_REAL_ID,
    YANDEX_TRACK_ID,
)


class MetadataWriteError(Exception):
    """Critical metadata enrichment failure for a newly downloaded MusicArk file."""


@dataclass(frozen=True, slots=True)
class Artwork:
    data: bytes
    mime: str


@dataclass(frozen=True, slots=True)
class MetadataWriteResult:
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class YandexTrackMetadata:
    provider_id: str
    external_id: str
    title: str | None = None
    version: str | None = None
    subtitle: str | None = None
    duration_seconds: float | None = None
    explicit: bool | None = None
    availability: str | None = None
    real_id: str | None = None
    source_url: str | None = None
    artists: tuple[str, ...] = ()
    artist_ids: tuple[str, ...] = ()
    album_id: str | None = None
    album_title: str | None = None
    album_artists: tuple[str, ...] = ()
    album_artist_ids: tuple[str, ...] = ()
    release_year: int | None = None
    release_date: str | None = None
    genre: str | None = None
    track_number: int | None = None
    total_tracks: int | None = None
    disc_number: int | None = None
    total_discs: int | None = None
    isrc: str | None = None
    publisher: str | None = None
    copyright: str | None = None
    cover_uri: str | None = None
    og_image: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def compact_snapshot(self) -> dict[str, Any]:
        """Small persisted task fallback; deliberately excludes provider-native raw data."""
        return {
            "provider": self.provider_id,
            "external_id": self.external_id,
            "real_id": self.real_id,
            "title": self.title,
            "version": self.version,
            "subtitle": self.subtitle,
            "duration_seconds": self.duration_seconds,
            "explicit": self.explicit,
            "availability": self.availability,
            "artists": list(self.artists),
            "artist_ids": list(self.artist_ids),
            "album_id": self.album_id,
            "album_title": self.album_title,
            "album_artists": list(self.album_artists),
            "album_artist_ids": list(self.album_artist_ids),
            "release_year": self.release_year,
            "release_date": self.release_date,
            "genre": self.genre,
            "track_number": self.track_number,
            "total_tracks": self.total_tracks,
            "disc_number": self.disc_number,
            "total_discs": self.total_discs,
            "isrc": self.isrc,
            "publisher": self.publisher,
            "copyright": self.copyright,
            "source_url": self.source_url,
            "cover_uri": self.cover_uri,
            "og_image": self.og_image,
        }

    def with_fallback(self, fallback: Mapping[str, Any] | None) -> "YandexTrackMetadata":
        """Fill only genuinely missing fresh fields from the immutable enqueue snapshot."""
        source = dict(fallback or {})

        def text(name: str, current: str | None) -> str | None:
            if current:
                return current
            value = source.get(name)
            return str(value).strip() if value is not None and str(value).strip() else None

        def texts(name: str, current: tuple[str, ...]) -> tuple[str, ...]:
            if current:
                return current
            value = source.get(name)
            if isinstance(value, (list, tuple)):
                return tuple(str(item).strip() for item in value if str(item).strip())
            return ()

        def integer(name: str, current: int | None) -> int | None:
            if current is not None:
                return current
            return _integer(source.get(name))

        duration = self.duration_seconds
        if duration is None:
            duration = _float(source.get("duration_seconds"))
        return YandexTrackMetadata(
            provider_id=self.provider_id,
            external_id=self.external_id,
            title=text("title", self.title),
            version=text("version", self.version),
            subtitle=text("subtitle", self.subtitle),
            duration_seconds=duration,
            explicit=self.explicit if self.explicit is not None else _boolean(source.get("explicit")),
            availability=text("availability", self.availability),
            real_id=text("real_id", self.real_id),
            source_url=text("source_url", self.source_url),
            artists=texts("artists", self.artists),
            artist_ids=texts("artist_ids", self.artist_ids),
            album_id=text("album_id", self.album_id),
            album_title=text("album_title", self.album_title),
            album_artists=texts("album_artists", self.album_artists),
            album_artist_ids=texts("album_artist_ids", self.album_artist_ids),
            release_year=integer("release_year", self.release_year),
            release_date=text("release_date", self.release_date),
            genre=text("genre", self.genre),
            track_number=integer("track_number", self.track_number),
            total_tracks=integer("total_tracks", self.total_tracks),
            disc_number=integer("disc_number", self.disc_number),
            total_discs=integer("total_discs", self.total_discs),
            isrc=text("isrc", self.isrc),
            publisher=text("publisher", self.publisher),
            copyright=text("copyright", self.copyright),
            cover_uri=text("cover_uri", self.cover_uri),
            og_image=text("og_image", self.og_image),
            raw_data=self.raw_data,
        )


def _dto_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
            if isinstance(data, dict):
                return dict(data)
        except Exception:  # noqa: BLE001 - provider DTOs vary across library versions.
            pass
    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        try:
            data = json.loads(to_json())
            if isinstance(data, dict):
                return dict(data)
        except Exception:  # noqa: BLE001
            pass
    return {}


def sanitize_yandex_raw_data(value: Any) -> Any:
    """Remove credential/transient-link shaped fields before provider metadata persistence."""
    blocked = {
        "authorization",
        "authtoken",
        "token",
        "cookie",
        "cookies",
        "directlink",
        "directurl",
        "downloadurl",
        "signedurl",
    }
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            compact_key = "".join(char for char in text_key.casefold() if char.isalnum())
            if any(marker in compact_key for marker in blocked):
                continue
            sanitized[text_key] = sanitize_yandex_raw_data(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [sanitize_yandex_raw_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_dto_dict(item) for item in value if _dto_dict(item)]


def _names_and_ids(value: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    names: list[str] = []
    ids: list[str] = []
    for item in _items(value):
        name = _text(item.get("name"))
        identity = _text(item.get("id"))
        if name:
            names.append(name)
        if identity:
            ids.append(identity)
    return tuple(names), tuple(ids)


def _first_text(*values: Any) -> str | None:
    for value in values:
        result = _text(value)
        if result:
            return result
    return None


def metadata_from_yandex_track(track: Any, *, fallback_external_id: str) -> YandexTrackMetadata:
    """Normalize only fields actually present in the full Yandex Track DTO."""
    raw = _dto_dict(track)
    safe_raw = sanitize_yandex_raw_data(raw)
    if not isinstance(safe_raw, dict):
        safe_raw = {}
    external_id = _first_text(raw.get("id"), fallback_external_id) or fallback_external_id
    artists, artist_ids = _names_and_ids(raw.get("artists"))
    albums = _items(raw.get("albums"))
    album = albums[0] if albums else {}
    album_artists, album_artist_ids = _names_and_ids(album.get("artists"))
    position = _dto_dict(album.get("track_position") or raw.get("track_position"))
    track_count_by_volume = album.get("track_count_by_volume")
    total_discs = len(track_count_by_volume) if isinstance(track_count_by_volume, (list, tuple)) else None
    duration_ms = _float(raw.get("duration_ms"))
    duration_seconds = duration_ms / 1000.0 if duration_ms is not None else None

    explicit: bool | None = _boolean(raw.get("explicit"))
    if explicit is None and raw.get("content_warning") is not None:
        explicit = bool(raw.get("content_warning"))
    available = _boolean(raw.get("available"))
    availability = "available" if available is True else ("unavailable" if available is False else None)

    release_year = _integer(album.get("year"))
    release_date = _text(album.get("release_date") or raw.get("release_date"))
    if release_year is None and release_date and len(release_date) >= 4:
        release_year = _integer(release_date[:4])

    metadata = _dto_dict(raw.get("meta_data"))
    major = _dto_dict(raw.get("major"))
    labels = _items(album.get("labels"))
    raw_label = raw.get("label")
    album_label = album.get("label")
    raw_label_name = (
        _text(raw_label) if isinstance(raw_label, str) else _text(_dto_dict(raw_label).get("name"))
    )
    album_label_name = (
        _text(album_label)
        if isinstance(album_label, str)
        else _text(_dto_dict(album_label).get("name"))
    )
    publisher = _first_text(
        raw_label_name,
        album_label_name,
        major.get("name"),
        labels[0].get("name") if labels else None,
    )
    copyright_value = _first_text(
        raw.get("copyright"),
        raw.get("copyright_cline"),
        album.get("copyright"),
        album.get("copyright_cline"),
    )
    album_id = _text(album.get("id"))
    source_url = (
        f"https://music.yandex.ru/album/{album_id}/track/{external_id}"
        if album_id and external_id
        else None
    )
    return YandexTrackMetadata(
        provider_id="yandex_music",
        external_id=external_id,
        title=_text(raw.get("title")),
        version=_text(raw.get("version")),
        subtitle=_text(raw.get("subtitle")),
        duration_seconds=duration_seconds,
        explicit=explicit,
        availability=availability,
        real_id=_text(raw.get("real_id")),
        source_url=source_url,
        artists=artists,
        artist_ids=artist_ids,
        album_id=album_id,
        album_title=_text(album.get("title")),
        album_artists=album_artists,
        album_artist_ids=album_artist_ids,
        release_year=release_year,
        release_date=release_date,
        genre=_first_text(album.get("genre"), raw.get("genre"), metadata.get("genre")),
        track_number=_integer(position.get("index") or raw.get("track_number")),
        total_tracks=_integer(album.get("track_count") or album.get("total_tracks")),
        disc_number=_integer(position.get("volume") or raw.get("disc_number")),
        total_discs=_integer(album.get("volume_count")) or total_discs,
        isrc=_first_text(raw.get("isrc"), metadata.get("isrc")),
        publisher=publisher,
        copyright=copyright_value,
        cover_uri=_first_text(raw.get("cover_uri"), album.get("cover_uri")),
        og_image=_first_text(raw.get("og_image"), album.get("og_image")),
        raw_data=dict(safe_raw),
    )


def yandex_artwork_url(metadata: YandexTrackMetadata, *, size: str = "1000x1000") -> str | None:
    value = metadata.cover_uri or metadata.og_image
    if not value:
        return None
    url = value.replace("%%", size)
    if url.startswith("//"):
        return f"https:{url}"
    if "://" not in url:
        return f"https://{url.lstrip('/')}"
    return url


class AudioMetadataWriter:
    """Write tags only to a file explicitly supplied by the current download operation."""

    def validate_audio(self, path: Path) -> None:
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(path))
            if audio is None or getattr(audio, "info", None) is None:
                raise MetadataWriteError("Downloaded file is not a parseable audio stream.")
        except MetadataWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MetadataWriteError("Downloaded file is not a parseable audio stream.") from exc

    def write_mp3(
        self,
        path: Path,
        metadata: YandexTrackMetadata,
        *,
        artwork: Artwork | None = None,
    ) -> MetadataWriteResult:
        if not metadata.title:
            raise MetadataWriteError("Critical metadata is missing: title.")
        if metadata.provider_id != "yandex_music" or not metadata.external_id:
            raise MetadataWriteError("Critical provider identity metadata is missing.")
        try:
            from mutagen.id3 import (
                APIC,
                ID3,
                ID3NoHeaderError,
                TALB,
                TCON,
                TCOP,
                TDRC,
                TIT2,
                TPE1,
                TPE2,
                TPOS,
                TPUB,
                TRCK,
                TSRC,
                TXXX,
            )

            try:
                tags = ID3(str(path))
            except ID3NoHeaderError:
                tags = ID3()

            for frame_id in ("TIT2", "TPE1", "TALB", "TPE2", "TRCK", "TPOS", "TDRC", "TCON", "TSRC", "TPUB", "TCOP"):
                tags.delall(frame_id)
            for frame in list(tags.getall("TXXX")):
                if str(getattr(frame, "desc", "")) in PROVENANCE_DESCRIPTIONS:
                    tags.delall(f"TXXX:{frame.desc}")

            tags.add(TIT2(encoding=3, text=[metadata.title]))
            if metadata.artists:
                tags.add(TPE1(encoding=3, text=list(metadata.artists)))
            if metadata.album_title:
                tags.add(TALB(encoding=3, text=[metadata.album_title]))
            if metadata.album_artists:
                tags.add(TPE2(encoding=3, text=list(metadata.album_artists)))
            if metadata.track_number is not None:
                value = str(metadata.track_number)
                if metadata.total_tracks is not None:
                    value += f"/{metadata.total_tracks}"
                tags.add(TRCK(encoding=3, text=[value]))
            if metadata.disc_number is not None:
                value = str(metadata.disc_number)
                if metadata.total_discs is not None:
                    value += f"/{metadata.total_discs}"
                tags.add(TPOS(encoding=3, text=[value]))
            date_value = metadata.release_date or (
                str(metadata.release_year) if metadata.release_year is not None else None
            )
            if date_value:
                tags.add(TDRC(encoding=3, text=[date_value]))
            if metadata.genre:
                tags.add(TCON(encoding=3, text=[metadata.genre]))
            if metadata.isrc:
                tags.add(TSRC(encoding=3, text=[metadata.isrc]))
            if metadata.publisher:
                tags.add(TPUB(encoding=3, text=[metadata.publisher]))
            if metadata.copyright:
                tags.add(TCOP(encoding=3, text=[metadata.copyright]))

            provenance = {
                MUSICARK_PROVIDER: metadata.provider_id,
                MUSICARK_EXTERNAL_ID: metadata.external_id,
                MUSICARK_METADATA_SCHEMA: MUSICARK_METADATA_SCHEMA_VERSION,
                YANDEX_TRACK_ID: metadata.external_id,
                YANDEX_REAL_ID: metadata.real_id,
                YANDEX_ALBUM_ID: metadata.album_id,
                YANDEX_ARTIST_IDS: ",".join(metadata.artist_ids) if metadata.artist_ids else None,
            }
            for description, value in provenance.items():
                if value:
                    tags.add(TXXX(encoding=3, desc=description, text=[value]))

            if artwork is not None:
                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=3,
                        mime=artwork.mime,
                        type=3,
                        desc="Cover",
                        data=artwork.data,
                    )
                )
            tags.save(str(path), v2_version=4)
            self.verify_critical(path, metadata)
        except MetadataWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MetadataWriteError("Failed to write critical MP3 metadata.") from exc
        return MetadataWriteResult()

    def verify_critical(self, path: Path, metadata: YandexTrackMetadata) -> None:
        try:
            from mutagen.id3 import ID3

            tags = ID3(str(path))
            title = tags.get("TIT2")
            if title is None or not title.text or str(title.text[0]) != metadata.title:
                raise MetadataWriteError("Critical title verification failed.")
            if metadata.artists:
                artist = tags.get("TPE1")
                actual = tuple(str(item) for item in (artist.text if artist is not None else ()))
                if actual != metadata.artists:
                    raise MetadataWriteError("Critical artist verification failed.")
            values: dict[str, str] = {}
            for frame in tags.getall("TXXX"):
                desc = str(getattr(frame, "desc", ""))
                text_values: Sequence[Any] = getattr(frame, "text", ())
                if desc and text_values:
                    values[desc] = str(text_values[0])
            if values.get(MUSICARK_PROVIDER) != metadata.provider_id:
                raise MetadataWriteError("Provider provenance verification failed.")
            if values.get(MUSICARK_EXTERNAL_ID) != metadata.external_id:
                raise MetadataWriteError("External-id provenance verification failed.")
            if values.get(YANDEX_TRACK_ID) != metadata.external_id:
                raise MetadataWriteError("Yandex-id provenance verification failed.")
            if values.get(MUSICARK_METADATA_SCHEMA) != MUSICARK_METADATA_SCHEMA_VERSION:
                raise MetadataWriteError("Metadata schema provenance verification failed.")
        except MetadataWriteError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MetadataWriteError("Failed to verify written MP3 metadata.") from exc
