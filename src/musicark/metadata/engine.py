"""Low-level metadata read/write using mutagen. See [[metadata-engine]]."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import shutil
import time
from typing import Any

from musicark.core.errors import MetadataEditorError

FIELD_MAX_LEN = 500
_YEAR_RE = re.compile(r"^[0-9]{4}")

_SUPPORTED_WRITE_EXT = frozenset({".mp3", ".flac", ".m4a", ".aac", ".mp4", ".ogg"})


def validate_text(field: str, value: Any, *, allow_empty: bool = True) -> str:
    if value is None and allow_empty:
        return ""
    if value is None:
        raise MetadataEditorError(f"Field '{field}' cannot be null.")
    s = str(value).strip()
    if len(s) > FIELD_MAX_LEN:
        raise MetadataEditorError(f"Field '{field}' exceeds maximum length ({FIELD_MAX_LEN}).")
    return s


def validate_year(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        y = int(value)
    except (TypeError, ValueError) as exc:
        raise MetadataEditorError("Year must be an integer.") from exc
    if y < 1800 or y > 2100:
        raise MetadataEditorError("Year must be between 1800 and 2100.")
    return y


def validate_track_number(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise MetadataEditorError("Track number must be an integer.") from exc
    if n < 1 or n > 999:
        raise MetadataEditorError("Track number must be between 1 and 999.")
    return n


def backup_audio_file(src: Path, backup_root: Path) -> Path:
    """Copy the full file next to originals for rollback."""
    backup_root.mkdir(parents=True, exist_ok=True)
    stem = src.stem[:80] if len(src.stem) > 80 else src.stem
    suffix = src.suffix.lower()
    stamp = int(time.time() * 1000)
    dest = backup_root / f"{stem}_musicark_backup_{stamp}{suffix}"
    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        raise MetadataEditorError(f"Failed to copy backup near '{backup_root}'.") from exc
    return dest


@dataclass(frozen=True)
class StructuredTags:
    title: str
    artist: str
    album: str
    track_number: str
    year: str
    genre: str
    has_cover: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "track_number": self.track_number,
            "year": self.year,
            "genre": self.genre,
            "has_cover": self.has_cover,
        }


def read_structured(path: Path) -> StructuredTags:
    ext = path.suffix.lower()
    if ext == ".mp3":
        return _read_mp3(path)
    if ext == ".flac":
        return _read_flac(path)
    if ext in {".m4a", ".aac", ".mp4"}:
        return _read_mp4(path)
    if ext == ".ogg":
        return _read_ogg_vorbis(path)
    if ext == ".wav":
        return StructuredTags(
            title="", artist="", album="", track_number="", year="", genre="", has_cover=False
        )
    raise MetadataEditorError(
        f"Metadata editor does not support this format yet: '{ext}'. "
        f"Try MP3, FLAC, M4A/MP4, or OGG."
    )


def _first(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, list):
        if not values:
            return ""
        return str(values[0])
    return str(values)


def _normalize_year(raw: str) -> str:
    if not raw:
        return ""
    m = _YEAR_RE.search(raw.strip())
    return m.group(0) if m else ""


def _read_mp3(path: Path) -> StructuredTags:
    from mutagen.id3 import APIC as ID3APIC  # noqa: N811
    from mutagen.mp3 import EasyMP3, MP3

    try:
        easy = EasyMP3(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot read MP3 tags: {path}") from exc
    full = MP3(str(path))
    has_cover = False
    if full.tags is not None:
        for key, frame in full.tags.items():
            key_s = key if isinstance(key, str) else getattr(key, "FrameID", str(key))
            if str(key_s).startswith("APIC") or isinstance(frame, ID3APIC):
                has_cover = True
                break
    return StructuredTags(
        title=_first(easy.get("title")),
        artist=_first(easy.get("artist")),
        album=_first(easy.get("album")),
        track_number=_first(easy.get("tracknumber")).split("/")[0].strip(),
        year=_normalize_year(_first(easy.get("date"))),
        genre=_first(easy.get("genre")),
        has_cover=has_cover,
    )


def _read_flac(path: Path) -> StructuredTags:
    from mutagen.flac import FLAC

    try:
        f = FLAC(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot read FLAC tags: {path}") from exc
    has_cover = bool(f.pictures)
    return StructuredTags(
        title=_first(f.get("title")),
        artist=_first(f.get("artist")),
        album=_first(f.get("album")),
        track_number=_first(f.get("tracknumber")).split("/")[0].strip(),
        year=_normalize_year(_first(f.get("date"))),
        genre=_first(f.get("genre")),
        has_cover=has_cover,
    )


def _read_mp4(path: Path) -> StructuredTags:
    from mutagen.mp4 import MP4

    try:
        m = MP4(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot read MP4/M4A tags: {path}") from exc
    covr = m.get("covr", [])
    has_cover = bool(covr)
    trkn = m.get("trkn", [(0, 0)])
    track = ""
    if trkn and isinstance(trkn[0], tuple):
        track = str(trkn[0][0]) if trkn[0][0] else ""
    return StructuredTags(
        title=_first(m.get("\xa9nam")),
        artist=_first(m.get("\xa9ART")),
        album=_first(m.get("\xa9alb")),
        track_number=track,
        year=_normalize_year(_first(m.get("\xa9day"))),
        genre=_first(m.get("\xa9gen")),
        has_cover=has_cover,
    )


def _read_ogg_vorbis(path: Path) -> StructuredTags:
    from mutagen.oggvorbis import OggVorbis

    try:
        o = OggVorbis(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot read OGG tags: {path}") from exc
    return StructuredTags(
        title=_first(o.get("title")),
        artist=_first(o.get("artist")),
        album=_first(o.get("album")),
        track_number=_first(o.get("tracknumber")).split("/")[0].strip(),
        year=_normalize_year(_first(o.get("date"))),
        genre=_first(o.get("genre")),
        has_cover=False,
    )


def apply_structured_patch(
    path: Path,
    *,
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    track_number: int | None = None,
    year: int | None = None,
    genre: str | None = None,
    clear_cover: bool = False,
    cover_image_path: str | None = None,
) -> tuple[StructuredTags, StructuredTags]:
    """Write allowed fields; returns (before, after)."""
    ext = path.suffix.lower()
    if ext not in _SUPPORTED_WRITE_EXT:
        raise MetadataEditorError(
            f"Writing metadata is not supported for '{ext}'. Supported: {sorted(_SUPPORTED_WRITE_EXT)}."
        )
    before = read_structured(path)
    cover_bytes: bytes | None = None
    if cover_image_path:
        cp = Path(cover_image_path)
        if not cp.is_file():
            raise MetadataEditorError(f"Cover image not found: {cp}")
        try:
            cover_bytes = cp.read_bytes()
        except OSError as exc:
            raise MetadataEditorError(f"Cannot read cover image: {cp}") from exc
        if len(cover_bytes) > 8 * 1024 * 1024:
            raise MetadataEditorError("Cover image is too large (max 8 MiB).")

    if ext == ".mp3":
        _write_mp3(path, title, artist, album, track_number, year, genre, clear_cover, cover_bytes)
    elif ext == ".flac":
        _write_flac(path, title, artist, album, track_number, year, genre, clear_cover, cover_bytes)
    elif ext in {".m4a", ".aac", ".mp4"}:
        _write_mp4(path, title, artist, album, track_number, year, genre, clear_cover, cover_bytes)
    elif ext == ".ogg":
        if clear_cover or cover_bytes:
            raise MetadataEditorError(
                "Embedded cover is not supported for OGG/Vorbis files in this version."
            )
        _write_ogg(path, title, artist, album, track_number, year, genre)

    after = read_structured(path)
    return before, after


def _write_mp3(
    path: Path,
    title: str | None,
    artist: str | None,
    album: str | None,
    track_number: int | None,
    year: int | None,
    genre: str | None,
    clear_cover: bool,
    cover_bytes: bytes | None,
) -> None:
    from mutagen.id3 import APIC, ID3
    from mutagen.mp3 import EasyMP3, MP3

    text_changed = any(v is not None for v in (title, artist, album, track_number, year, genre))
    if text_changed:
        try:
            audio = EasyMP3(str(path))
            if audio.tags is None:
                audio.add_tags()
            if title is not None:
                audio["title"] = title
            if artist is not None:
                audio["artist"] = artist
            if album is not None:
                audio["album"] = album
            if track_number is not None:
                audio["tracknumber"] = str(track_number)
            if year is not None:
                audio["date"] = str(year)
            if genre is not None:
                audio["genre"] = genre
            audio.save()
        except Exception as exc:  # noqa: BLE001
            raise MetadataEditorError(f"Failed to write MP3 tags: {path}") from exc

    if not clear_cover and cover_bytes is None:
        return

    try:
        mid = MP3(str(path), ID3=ID3)
        if mid.tags is None:
            mid.add_tags()
        for key in list(mid.tags.keys()):
            ks = key if isinstance(key, str) else str(getattr(key, "FrameID", key))
            if ks.startswith("APIC"):
                del mid.tags[key]
        if cover_bytes is not None:
            mid.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=cover_bytes,
                )
            )
        mid.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Failed to update MP3 cover art: {path}") from exc


def _write_flac(
    path: Path,
    title: str | None,
    artist: str | None,
    album: str | None,
    track_number: int | None,
    year: int | None,
    genre: str | None,
    clear_cover: bool,
    cover_bytes: bytes | None,
) -> None:
    from mutagen.flac import FLAC, Picture

    try:
        f = FLAC(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot open FLAC: {path}") from exc
    if any(v is not None for v in (title, artist, album, track_number, year, genre)):
        if title is not None:
            f["title"] = [title]
        if artist is not None:
            f["artist"] = [artist]
        if album is not None:
            f["album"] = [album]
        if track_number is not None:
            f["tracknumber"] = [str(track_number)]
        if year is not None:
            f["date"] = [str(year)]
        if genre is not None:
            f["genre"] = [genre]
    if clear_cover or cover_bytes is not None:
        f.clear_pictures()
    if cover_bytes is not None:
        pic = Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.desc = "Cover"
        pic.data = cover_bytes
        f.add_picture(pic)
    try:
        f.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Failed to save FLAC tags: {path}") from exc


def _write_mp4(
    path: Path,
    title: str | None,
    artist: str | None,
    album: str | None,
    track_number: int | None,
    year: int | None,
    genre: str | None,
    clear_cover: bool,
    cover_bytes: bytes | None,
) -> None:
    from mutagen.mp4 import MP4, MP4Cover

    try:
        m = MP4(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot open MP4/M4A: {path}") from exc
    if any(v is not None for v in (title, artist, album, track_number, year, genre)):
        if title is not None:
            m["\xa9nam"] = [title]
        if artist is not None:
            m["\xa9ART"] = [artist]
        if album is not None:
            m["\xa9alb"] = [album]
        if track_number is not None:
            m["trkn"] = [(track_number, 0)]
        if year is not None:
            m["\xa9day"] = [str(year)]
        if genre is not None:
            m["\xa9gen"] = [genre]
    if clear_cover:
        if "covr" in m:
            del m["covr"]
    if cover_bytes is not None:
        m["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
    try:
        m.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Failed to save MP4/M4A tags: {path}") from exc


def _write_ogg(
    path: Path,
    title: str | None,
    artist: str | None,
    album: str | None,
    track_number: int | None,
    year: int | None,
    genre: str | None,
) -> None:
    from mutagen.oggvorbis import OggVorbis

    try:
        o = OggVorbis(str(path))
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Cannot open OGG: {path}") from exc
    if title is not None:
        o["title"] = title
    if artist is not None:
        o["artist"] = artist
    if album is not None:
        o["album"] = album
    if track_number is not None:
        o["tracknumber"] = str(track_number)
    if year is not None:
        o["date"] = str(year)
    if genre is not None:
        o["genre"] = genre
    try:
        o.save()
    except Exception as exc:  # noqa: BLE001
        raise MetadataEditorError(f"Failed to save OGG tags: {path}") from exc
