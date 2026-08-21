"""Read-only technical audio probing built on the existing Mutagen dependency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formats import capabilities_for_path


@dataclass(frozen=True, slots=True)
class AudioTechnicalInfo:
    format: str
    container: str
    codec: str
    duration_seconds: float | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    bit_depth: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "container": self.container,
            "codec": self.codec,
            "durationSeconds": self.duration_seconds,
            "bitrate": self.bitrate,
            "sampleRate": self.sample_rate,
            "channels": self.channels,
            "bitDepth": self.bit_depth,
        }


def _positive(value: Any, cast):  # type: ignore[no-untyped-def]
    try:
        converted = cast(value)
    except (TypeError, ValueError):
        return None
    return converted if converted > 0 else None


def probe_audio(path: Path) -> AudioTechnicalInfo:
    capability = capabilities_for_path(path)
    if capability is None:
        raise ValueError(f"Unsupported audio format: {path.suffix}")
    from mutagen import File as MutagenFile

    audio = MutagenFile(str(path))
    if audio is None or getattr(audio, "info", None) is None:
        raise ValueError(f"Unsupported or corrupted audio file: {path}")
    info = audio.info
    duration = _positive(getattr(info, "length", None), float)
    bitrate = _positive(
        getattr(info, "bitrate", None) or getattr(info, "bitrate_nominal", None), int
    )
    sample_rate = _positive(getattr(info, "sample_rate", None), int)
    channels = _positive(getattr(info, "channels", None), int)
    # Bit depth is meaningful for the lossless PCM-like formats where Mutagen
    # exposes it directly. It is deliberately omitted for perceptual codecs.
    bit_depth = None
    if capability.format in {"flac", "wav"}:
        bit_depth = _positive(
            getattr(info, "bits_per_sample", None) or getattr(info, "bitdepth", None), int
        )
    raw_codec = str(
        getattr(info, "codec_description", None)
        or getattr(info, "codec", None)
        or capability.format
    ).strip()
    return AudioTechnicalInfo(
        format=capability.format,
        container=capability.display_name,
        codec=raw_codec or capability.format,
        duration_seconds=duration,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
    )
