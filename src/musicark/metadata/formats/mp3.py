"""MP3/ID3 adapter preserving unedited frames and the MPEG audio stream."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

from musicark.provenance import PROVENANCE_DESCRIPTIONS

from .base import MetadataFormatAdapter, MetadataFormatError


_YEAR_RE = re.compile(r"(18|19|20|21)\d{2}")


def _texts(frame: Any) -> list[str]:
    values = getattr(frame, "text", ())
    if isinstance(values, str):
        return [values]
    try:
        return [str(item) for item in values]
    except TypeError:
        return [str(values)] if values is not None else []


def _first(tags: Any, key: str) -> str | None:
    frame = tags.get(key) if tags is not None else None
    values = _texts(frame) if frame is not None else []
    value = values[0].strip() if values else ""
    return value or None


def _split_pair(raw: str | None) -> tuple[int | None, int | None]:
    if not raw:
        return None, None
    left, _, right = raw.partition("/")
    try:
        current = int(left.strip()) if left.strip() else None
    except ValueError:
        current = None
    try:
        total = int(right.strip()) if right.strip() else None
    except ValueError:
        total = None
    return current, total


def _txxx(tags: Any, description: str) -> str | None:
    for frame in tags.getall("TXXX") if tags is not None else ():
        if str(getattr(frame, "desc", "")) == description:
            values = _texts(frame)
            return values[0].strip() if values and values[0].strip() else None
    return None


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


class Mp3MetadataAdapter(MetadataFormatAdapter):
    """Full v8.2.0 writer. All mutations happen on a caller-owned temporary copy."""

    extensions = frozenset({".mp3"})

    @staticmethod
    def _load(path: Path):  # type: ignore[no-untyped-def]
        from mutagen.id3 import ID3, ID3NoHeaderError

        try:
            return ID3(str(path))
        except ID3NoHeaderError:
            return ID3()
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Cannot read ID3 tags: {path}") from exc

    def read(self, path: Path) -> dict[str, Any]:
        tags = self._load(path)
        track_number, total_tracks = _split_pair(_first(tags, "TRCK"))
        disc_number, total_discs = _split_pair(_first(tags, "TPOS"))
        release_date = _first(tags, "TDRC")
        year = None
        if release_date:
            match = _YEAR_RE.search(release_date)
            year = int(match.group(0)) if match else None

        comments = tags.getall("COMM")
        lyrics_frames = tags.getall("USLT")
        comment = str(getattr(comments[0], "text", "")).strip() if comments else None
        lyrics = str(getattr(lyrics_frames[0], "text", "")).strip() if lyrics_frames else None
        explicit_raw = _txxx(tags, "MUSICARK_EXPLICIT") or _txxx(tags, "ITUNESADVISORY")
        explicit = None
        if explicit_raw is not None:
            explicit = explicit_raw.strip().casefold() in {"1", "true", "yes", "explicit"}

        fields: dict[str, Any] = {
            "title": _first(tags, "TIT2"),
            "subtitle": _first(tags, "TIT3"),
            "version": _txxx(tags, "VERSION"),
            "artists": _texts(tags.get("TPE1")) if tags.get("TPE1") is not None else [],
            "album": _first(tags, "TALB"),
            "albumArtists": _texts(tags.get("TPE2")) if tags.get("TPE2") is not None else [],
            "trackNumber": track_number,
            "totalTracks": total_tracks,
            "discNumber": disc_number,
            "totalDiscs": total_discs,
            "releaseDate": release_date,
            "year": year,
            "genres": _texts(tags.get("TCON")) if tags.get("TCON") is not None else [],
            "isrc": _first(tags, "TSRC"),
            "publisher": _first(tags, "TPUB"),
            "label": _txxx(tags, "LABEL"),
            "copyright": _first(tags, "TCOP"),
            "composer": _first(tags, "TCOM"),
            "lyricist": _first(tags, "TEXT"),
            "bpm": _first(tags, "TBPM"),
            "comment": comment,
            "grouping": _first(tags, "TIT1"),
            "lyrics": lyrics,
            "explicit": explicit,
        }
        all_tags: list[dict[str, Any]] = []
        from mutagen.id3 import TextFrame

        for key, frame in tags.items():
            frame_id = str(getattr(frame, "FrameID", key)).split(":", 1)[0]
            if isinstance(frame, TextFrame):
                description = str(getattr(frame, "desc", "")) or None
                all_tags.append(
                    {
                        "key": str(key),
                        "frameId": frame_id,
                        "description": description,
                        "values": _texts(frame),
                        "editable": not bool(description in PROVENANCE_DESCRIPTIONS),
                        "provenance": bool(description in PROVENANCE_DESCRIPTIONS),
                    }
                )
            elif frame_id == "COMM":
                all_tags.append(
                    {
                        "key": str(key),
                        "frameId": "COMM",
                        "description": str(getattr(frame, "desc", "")) or None,
                        "values": [str(getattr(frame, "text", ""))],
                        "editable": True,
                        "provenance": False,
                    }
                )
            elif frame_id == "USLT":
                all_tags.append(
                    {
                        "key": str(key),
                        "frameId": "USLT",
                        "description": str(getattr(frame, "desc", "")) or None,
                        "values": [str(getattr(frame, "text", ""))],
                        "editable": True,
                        "provenance": False,
                    }
                )
            else:
                all_tags.append(
                    {
                        "key": str(key),
                        "frameId": frame_id,
                        "description": None,
                        "values": [],
                        "editable": False,
                        "provenance": False,
                    }
                )
        return {"fields": fields, "allTags": all_tags}

    @staticmethod
    def _set_frame(tags: Any, frame_id: str, frame_class: Any, values: Iterable[str]) -> None:
        tags.delall(frame_id)
        text = [str(item) for item in values if str(item) != ""]
        if text:
            tags.add(frame_class(encoding=3, text=text))

    @staticmethod
    def _set_txxx(tags: Any, description: str, values: Iterable[str]) -> None:
        from mutagen.id3 import TXXX

        tags.delall(f"TXXX:{description}")
        text = [str(item) for item in values if str(item) != ""]
        if text:
            tags.add(TXXX(encoding=3, desc=description, text=text))

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
        from mutagen.id3 import (
            APIC, COMM, Frames, TALB, TBPM, TCOM, TCON, TCOP, TDRC, TEXT,
            TIT1, TIT2, TIT3, TPE1, TPE2, TPOS, TPUB, TRCK, TSRC, TextFrame, USLT,
        )

        tags = self._load(path)
        simple = {
            "title": ("TIT2", TIT2),
            "subtitle": ("TIT3", TIT3),
            "artists": ("TPE1", TPE1),
            "album": ("TALB", TALB),
            "albumArtists": ("TPE2", TPE2),
            "genres": ("TCON", TCON),
            "isrc": ("TSRC", TSRC),
            "publisher": ("TPUB", TPUB),
            "copyright": ("TCOP", TCOP),
            "composer": ("TCOM", TCOM),
            "lyricist": ("TEXT", TEXT),
            "bpm": ("TBPM", TBPM),
            "grouping": ("TIT1", TIT1),
        }
        for name, (frame_id, frame_class) in simple.items():
            if name in changes:
                self._set_frame(tags, frame_id, frame_class, _as_text_list(changes.get(name)))

        if "version" in changes:
            self._set_txxx(tags, "VERSION", _as_text_list(changes.get("version")))
        if "label" in changes:
            self._set_txxx(tags, "LABEL", _as_text_list(changes.get("label")))
        if "explicit" in changes:
            value = changes.get("explicit")
            self._set_txxx(tags, "MUSICARK_EXPLICIT", [] if value is None else ["1" if bool(value) else "0"])

        if "trackNumber" in changes or "totalTracks" in changes:
            current, total = _split_pair(_first(tags, "TRCK"))
            current = changes.get("trackNumber", current)
            total = changes.get("totalTracks", total)
            value = ""
            if current not in (None, ""):
                value = str(int(current))
                if total not in (None, ""):
                    value += f"/{int(total)}"
            self._set_frame(tags, "TRCK", TRCK, [value] if value else [])

        if "discNumber" in changes or "totalDiscs" in changes:
            current, total = _split_pair(_first(tags, "TPOS"))
            current = changes.get("discNumber", current)
            total = changes.get("totalDiscs", total)
            value = ""
            if current not in (None, ""):
                value = str(int(current))
                if total not in (None, ""):
                    value += f"/{int(total)}"
            self._set_frame(tags, "TPOS", TPOS, [value] if value else [])

        if "releaseDate" in changes:
            self._set_frame(tags, "TDRC", TDRC, _as_text_list(changes.get("releaseDate")))
        elif "year" in changes:
            self._set_frame(tags, "TDRC", TDRC, _as_text_list(changes.get("year")))

        if "comment" in changes:
            tags.delall("COMM")
            value = str(changes.get("comment") or "")
            if value:
                tags.add(COMM(encoding=3, lang="eng", desc="MusicArk", text=value))
        if "lyrics" in changes:
            tags.delall("USLT")
            value = str(changes.get("lyrics") or "")
            if value:
                tags.add(USLT(encoding=3, lang="eng", desc="MusicArk", text=value))

        # Advanced editor operations are opt-in. Basic saves therefore preserve all
        # unknown/custom frames exactly as they were on the copied file.
        if "deleteTextFrames" in changes:
            for raw in changes.get("deleteTextFrames") or []:
                key = str(raw).strip()
                if key.startswith("TXXX:") and key.split(":", 1)[1] in PROVENANCE_DESCRIPTIONS:
                    raise MetadataFormatError("MusicArk provenance tags can only change through Apply + Bind.")
                if key:
                    tags.delall(key)
        if "textFrames" in changes:
            raw_frames = changes.get("textFrames") or {}
            if isinstance(raw_frames, dict):
                for frame_id, raw_values in raw_frames.items():
                    frame_key = str(frame_id).upper().strip()
                    frame_class = Frames.get(frame_key)
                    if frame_class is None or frame_key == "TXXX" or not issubclass(frame_class, TextFrame):
                        raise MetadataFormatError(f"Unsupported editable ID3 text frame: {frame_key}")
                    self._set_frame(tags, frame_key, frame_class, _as_text_list(raw_values))
        if "customTextTags" in changes:
            # Replace only named TXXX descriptions supplied by the caller; omitted
            # TXXX frames remain untouched unless explicitly listed for deletion.
            for item in changes.get("customTextTags") or []:
                if not isinstance(item, dict):
                    continue
                desc = str(item.get("description") or "").strip()
                if not desc:
                    raise MetadataFormatError("Custom text tags require a description.")
                if desc in PROVENANCE_DESCRIPTIONS:
                    raise MetadataFormatError("MusicArk provenance tags can only change through Apply + Bind.")
                self._set_txxx(tags, desc, _as_text_list(item.get("values")))

        if remove_artwork or artwork_data is not None:
            # Only replace front covers. Other embedded pictures are intentionally kept.
            for key, frame in list(tags.items()):
                if str(getattr(frame, "FrameID", "")) == "APIC" and int(getattr(frame, "type", 0)) == 3:
                    del tags[key]
            if artwork_data is not None:
                tags.add(
                    APIC(
                        encoding=3,
                        mime=artwork_mime or "image/jpeg",
                        type=3,
                        desc="Cover",
                        data=artwork_data,
                    )
                )

        if provenance is not None:
            for description in PROVENANCE_DESCRIPTIONS:
                tags.delall(f"TXXX:{description}")
            for description, value in provenance.items():
                if value:
                    self._set_txxx(tags, description, [value])

        try:
            tags.save(str(path), v2_version=4)
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"Failed to write ID3 tags: {path}") from exc

    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        tags = self._load(path)
        frames = list(tags.getall("APIC"))
        if not frames:
            return None
        front = next((frame for frame in frames if int(getattr(frame, "type", 0)) == 3), frames[0])
        data = bytes(getattr(front, "data", b""))
        if not data:
            return None
        return data, str(getattr(front, "mime", "image/jpeg") or "image/jpeg")

    def validate_audio(self, path: Path) -> float | None:
        try:
            from mutagen.mp3 import MP3

            audio = MP3(str(path))
            info = getattr(audio, "info", None)
            if info is None:
                raise MetadataFormatError("MP3 audio stream is missing.")
            length = getattr(info, "length", None)
            return float(length) if length is not None else None
        except MetadataFormatError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MetadataFormatError(f"MP3 audio validation failed: {path}") from exc
