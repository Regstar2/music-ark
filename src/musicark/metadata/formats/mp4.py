"""M4A/MP4 atom adapter for normalized MusicArk metadata."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .base import MetadataFormatAdapter, MetadataFormatError

_YEAR_RE = re.compile(r"(18|19|20|21)\d{2}")


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _first(tags: Any, key: str) -> str | None:
    values = _list(tags.get(key) if tags else None)
    return values[0] if values else None


def _number_pair(tags: Any, key: str) -> tuple[int | None, int | None]:
    raw = tags.get(key) if tags else None
    if not raw:
        return None, None
    try:
        current, total = raw[0][:2]
        return (int(current) or None, int(total) or None)
    except (TypeError, ValueError, IndexError):
        return None, None


class Mp4MetadataAdapter(MetadataFormatAdapter):
    """Read/write the common MP4 atoms used by M4A audio files."""

    extensions = frozenset({".m4a", ".mp4"})

    @staticmethod
    def _load(path: Path):  # type: ignore[no-untyped-def]
        try:
            from mutagen.mp4 import MP4

            return MP4(str(path))
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Cannot read MP4 metadata: {path}") from exc

    def read(self, path: Path) -> dict[str, Any]:
        audio = self._load(path)
        tags = audio.tags or {}
        track, total_tracks = _number_pair(tags, "trkn")
        disc, total_discs = _number_pair(tags, "disk")
        release_date = _first(tags, "\xa9day")
        year = None
        if release_date:
            match = _YEAR_RE.search(release_date)
            year = int(match.group(0)) if match else None
        fields = {
            "title": _first(tags, "\xa9nam"),
            "artists": _list(tags.get("\xa9ART")),
            "album": _first(tags, "\xa9alb"),
            "albumArtists": _list(tags.get("aART")),
            "trackNumber": track,
            "totalTracks": total_tracks,
            "discNumber": disc,
            "totalDiscs": total_discs,
            "releaseDate": release_date,
            "year": year,
            "genres": _list(tags.get("\xa9gen")),
            "composer": _first(tags, "\xa9wrt"),
            "comment": _first(tags, "\xa9cmt"),
            "lyrics": _first(tags, "\xa9lyr"),
        }
        all_tags = []
        for key in sorted(tags, key=str):
            raw = tags.get(key)
            all_tags.append(
                {
                    "key": str(key),
                    "frameId": str(key),
                    "description": None,
                    "values": [] if key == "covr" else _list(raw),
                    "editable": key != "covr",
                    "provenance": str(key).startswith("----:com.musicark:"),
                }
            )
        return {"fields": fields, "allTags": all_tags}

    @staticmethod
    def _set(tags: Any, key: str, values: list[str]) -> None:
        if values:
            tags[key] = values
        else:
            tags.pop(key, None)

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
        audio = self._load(path)
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        assert tags is not None
        mapping = {
            "title": "\xa9nam",
            "artists": "\xa9ART",
            "album": "\xa9alb",
            "albumArtists": "aART",
            "genres": "\xa9gen",
            "composer": "\xa9wrt",
            "comment": "\xa9cmt",
            "lyrics": "\xa9lyr",
        }
        for field, atom in mapping.items():
            if field in changes:
                self._set(tags, atom, _list(changes.get(field)))
        if "trackNumber" in changes or "totalTracks" in changes:
            current, total = _number_pair(tags, "trkn")
            current = changes.get("trackNumber", current)
            total = changes.get("totalTracks", total)
            if current in (None, ""):
                tags.pop("trkn", None)
            else:
                tags["trkn"] = [(int(current), int(total or 0))]
        if "discNumber" in changes or "totalDiscs" in changes:
            current, total = _number_pair(tags, "disk")
            current = changes.get("discNumber", current)
            total = changes.get("totalDiscs", total)
            if current in (None, ""):
                tags.pop("disk", None)
            else:
                tags["disk"] = [(int(current), int(total or 0))]
        if "releaseDate" in changes:
            self._set(tags, "\xa9day", _list(changes.get("releaseDate")))
        elif "year" in changes:
            self._set(tags, "\xa9day", _list(changes.get("year")))

        if provenance:
            for key, value in provenance.items():
                atom = f"----:com.musicark:{str(key).strip().casefold()}"
                if value:
                    tags[atom] = [str(value).encode("utf-8")]
                else:
                    tags.pop(atom, None)

        if remove_artwork or artwork_data is not None:
            tags.pop("covr", None)
            if artwork_data is not None:
                from mutagen.mp4 import MP4Cover

                mime = str(artwork_mime or "").casefold()
                if mime == "image/png" or artwork_data.startswith(b"\x89PNG"):
                    image_format = MP4Cover.FORMAT_PNG
                elif mime in {"image/jpeg", "image/jpg"} or artwork_data.startswith(b"\xff\xd8"):
                    image_format = MP4Cover.FORMAT_JPEG
                else:
                    raise MetadataFormatError("Artwork must be PNG or JPEG.")
                tags["covr"] = [MP4Cover(artwork_data, imageformat=image_format)]
        try:
            audio.save()
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Failed to write MP4 metadata: {path}") from exc

    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        audio = self._load(path)
        covers = list((audio.tags or {}).get("covr", []))
        if not covers:
            return None
        cover = covers[0]
        data = bytes(cover)
        if not data:
            return None
        image_format = int(getattr(cover, "imageformat", 0) or 0)
        try:
            from mutagen.mp4 import MP4Cover

            mime = "image/png" if image_format == MP4Cover.FORMAT_PNG else "image/jpeg"
        except Exception:  # noqa: BLE001
            mime = "image/jpeg"
        return data, mime

    def validate_audio(self, path: Path) -> float | None:
        audio = self._load(path)
        info = getattr(audio, "info", None)
        if info is None:
            raise MetadataFormatError("MP4 audio stream is missing.")
        length = getattr(info, "length", None)
        return float(length) if length is not None else None
