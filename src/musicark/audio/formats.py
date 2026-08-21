"""Single source of truth for local-audio capabilities.

UI, metadata editing, upload and recovery must query this registry rather than
repeating extension checks. Capabilities are intentionally conservative: a
write capability is advertised only when MusicArk has a dedicated Mutagen
adapter for that container.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AudioFormatCapabilities:
    """Stable application-facing capabilities for one audio container family."""

    format: str
    display_name: str
    extensions: frozenset[str]
    can_read_metadata: bool
    can_write_metadata: bool
    can_read_artwork: bool
    can_write_artwork: bool
    can_fingerprint: bool
    can_play: bool
    can_upload_directly: bool
    can_transcode_for_yandex: bool
    lossless: bool

    @property
    def metadata_mode(self) -> str:
        return "writable" if self.can_write_metadata else "read_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "displayName": self.display_name,
            "extensions": sorted(self.extensions),
            "canReadMetadata": self.can_read_metadata,
            "canWriteMetadata": self.can_write_metadata,
            "canReadArtwork": self.can_read_artwork,
            "canWriteArtwork": self.can_write_artwork,
            "canFingerprint": self.can_fingerprint,
            "canPlay": self.can_play,
            "canUploadDirectly": self.can_upload_directly,
            "canTranscodeForYandex": self.can_transcode_for_yandex,
            "metadataMode": self.metadata_mode,
            "lossless": self.lossless,
        }


AUDIO_FORMAT_CAPABILITIES: tuple[AudioFormatCapabilities, ...] = (
    AudioFormatCapabilities(
        "mp3", "MP3", frozenset({".mp3"}), True, True, True, True,
        True, True, True, False, False,
    ),
    AudioFormatCapabilities(
        "flac", "FLAC", frozenset({".flac"}), True, True, True, True,
        True, True, False, True, True,
    ),
    AudioFormatCapabilities(
        "m4a", "M4A / MP4 Audio", frozenset({".m4a", ".mp4"}), True, True, True, True,
        True, True, False, True, False,
    ),
    AudioFormatCapabilities(
        "aac", "AAC", frozenset({".aac"}), True, False, False, False,
        True, True, False, True, False,
    ),
    AudioFormatCapabilities(
        "ogg", "OGG Vorbis", frozenset({".ogg"}), True, True, True, True,
        True, True, False, True, False,
    ),
    AudioFormatCapabilities(
        "opus", "Opus", frozenset({".opus"}), True, True, True, True,
        True, True, False, True, False,
    ),
    AudioFormatCapabilities(
        "wav", "WAV", frozenset({".wav"}), True, False, False, False,
        True, True, False, True, True,
    ),
)

_BY_EXTENSION = {
    extension: capabilities
    for capabilities in AUDIO_FORMAT_CAPABILITIES
    for extension in capabilities.extensions
}


def normalize_extension(value: str | Path) -> str:
    text = str(value).strip().casefold()
    if not text:
        return ""
    if any(separator in text for separator in ("/", "\\")):
        text = Path(text).suffix.casefold()
    elif not text.startswith("."):
        text = f".{text}"
    return text


def capabilities_for_extension(extension: str | Path) -> AudioFormatCapabilities | None:
    """Resolve an extension fail-closed; unknown formats return ``None``."""
    return _BY_EXTENSION.get(normalize_extension(extension))


def capabilities_for_path(path: Path) -> AudioFormatCapabilities | None:
    return capabilities_for_extension(path.suffix)


def supported_extensions() -> frozenset[str]:
    return frozenset(_BY_EXTENSION)
