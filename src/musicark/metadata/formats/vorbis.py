"""FLAC/Vorbis-comment adapters for normalized MusicArk metadata."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .base import MetadataFormatAdapter, MetadataFormatError
from .generic import normalized_easy_fields, validate_generic_audio


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _pair(current: Any, total: Any) -> list[str]:
    if current in (None, ""):
        return []
    value = str(int(current))
    if total not in (None, ""):
        value += f"/{int(total)}"
    return [value]


def _mime_for(data: bytes, mime: str | None) -> str:
    value = str(mime or "").split(";", 1)[0].strip().casefold()
    if value in {"image/jpeg", "image/png"}:
        return value
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    raise MetadataFormatError("Artwork must be PNG or JPEG.")


class VorbisMetadataAdapter(MetadataFormatAdapter):
    """Write normalized fields to FLAC, Ogg Vorbis or Ogg Opus comments."""

    def __init__(self, extension: str) -> None:
        clean = extension.casefold()
        if clean not in {".flac", ".ogg", ".opus"}:
            raise ValueError("Unsupported Vorbis-comment adapter extension.")
        self.extensions = frozenset({clean})
        self._extension = clean

    def _load(self, path: Path):  # type: ignore[no-untyped-def]
        try:
            if self._extension == ".flac":
                from mutagen.flac import FLAC

                return FLAC(str(path))
            if self._extension == ".ogg":
                from mutagen.oggvorbis import OggVorbis

                return OggVorbis(str(path))
            from mutagen.oggopus import OggOpus

            return OggOpus(str(path))
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Cannot read {self._extension} metadata: {path}") from exc

    def read(self, path: Path) -> dict[str, Any]:
        audio = self._load(path)
        fields = normalized_easy_fields(path)
        tags = getattr(audio, "tags", None)
        all_tags: list[dict[str, Any]] = []
        if tags:
            for key in sorted(tags.keys(), key=lambda item: str(item).casefold()):
                name = str(key)
                values = _string_list(tags.get(key))
                all_tags.append(
                    {
                        "key": name,
                        "frameId": name,
                        "description": None,
                        "values": [] if name.casefold() == "metadata_block_picture" else values,
                        "editable": name.casefold() != "metadata_block_picture",
                        "provenance": name.casefold().startswith("musicark_"),
                    }
                )
        return {"fields": fields, "allTags": all_tags}

    @staticmethod
    def _set(tags: Any, key: str, values: list[str]) -> None:
        if values:
            tags[key] = values
        elif key in tags:
            del tags[key]

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
        if getattr(audio, "tags", None) is None:
            try:
                audio.add_tags()
            except Exception as exc:  # noqa: BLE001
                raise MetadataFormatError("This audio file cannot accept Vorbis comments.") from exc
        tags = audio.tags
        assert tags is not None
        mapping = {
            "title": "title",
            "artists": "artist",
            "album": "album",
            "albumArtists": "albumartist",
            "genres": "genre",
            "composer": "composer",
            "comment": "comment",
            "lyrics": "lyrics",
        }
        for field, key in mapping.items():
            if field in changes:
                self._set(tags, key, _string_list(changes.get(field)))
        if "trackNumber" in changes or "totalTracks" in changes:
            current = changes.get("trackNumber", normalized_easy_fields(path).get("trackNumber"))
            total = changes.get("totalTracks", normalized_easy_fields(path).get("totalTracks"))
            self._set(tags, "tracknumber", _pair(current, total))
        if "discNumber" in changes or "totalDiscs" in changes:
            current = changes.get("discNumber", normalized_easy_fields(path).get("discNumber"))
            total = changes.get("totalDiscs", normalized_easy_fields(path).get("totalDiscs"))
            self._set(tags, "discnumber", _pair(current, total))
        if "releaseDate" in changes:
            self._set(tags, "date", _string_list(changes.get("releaseDate")))
        elif "year" in changes:
            self._set(tags, "date", _string_list(changes.get("year")))

        if provenance:
            for description, value in provenance.items():
                key = str(description).strip().casefold()
                if key:
                    self._set(tags, key, _string_list(value))

        if self._extension == ".flac":
            if remove_artwork or artwork_data is not None:
                preserved = [picture for picture in list(getattr(audio, "pictures", [])) if int(getattr(picture, "type", 0)) != 3]
                audio.clear_pictures()
                for picture in preserved:
                    audio.add_picture(picture)
                if artwork_data is not None:
                    from mutagen.flac import Picture

                    picture = Picture()
                    picture.type = 3
                    picture.mime = _mime_for(artwork_data, artwork_mime)
                    picture.desc = "Cover"
                    picture.data = artwork_data
                    audio.add_picture(picture)
        elif remove_artwork or artwork_data is not None:
            tags.pop("metadata_block_picture", None)
            if artwork_data is not None:
                from mutagen.flac import Picture

                picture = Picture()
                picture.type = 3
                picture.mime = _mime_for(artwork_data, artwork_mime)
                picture.desc = "Cover"
                picture.data = artwork_data
                tags["metadata_block_picture"] = [
                    base64.b64encode(picture.write()).decode("ascii")
                ]
        try:
            audio.save()
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Failed to write metadata: {path}") from exc

    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        audio = self._load(path)
        if self._extension == ".flac":
            pictures = list(getattr(audio, "pictures", []))
            if not pictures:
                return None
            picture = next((item for item in pictures if int(getattr(item, "type", 0)) == 3), pictures[0])
            data = bytes(getattr(picture, "data", b""))
            return (data, str(getattr(picture, "mime", "image/jpeg") or "image/jpeg")) if data else None
        tags = getattr(audio, "tags", None)
        values = list(tags.get("metadata_block_picture", [])) if tags else []
        if not values:
            return None
        from mutagen.flac import Picture

        for raw in values:
            try:
                picture = Picture(base64.b64decode(str(raw), validate=True))
            except Exception:  # noqa: BLE001 - malformed optional picture is ignored
                continue
            data = bytes(getattr(picture, "data", b""))
            if data and int(getattr(picture, "type", 0)) == 3:
                return data, str(getattr(picture, "mime", "image/jpeg") or "image/jpeg")
        return None

    def validate_audio(self, path: Path) -> float | None:
        return validate_generic_audio(path)
