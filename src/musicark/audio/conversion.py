"""Safe temporary MP3 conversion for the Yandex upload boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any

from musicark.metadata.formats.mp3 import Mp3MetadataAdapter
from musicark.metadata.formats.registry import MetadataAdapterRegistry

from .ffmpeg import FFmpegLocator, FFmpegRunner, FFmpegStatus
from .formats import AudioFormatCapabilities, capabilities_for_path
from .probe import AudioTechnicalInfo, probe_audio


class ConversionErrorCode(str, Enum):
    FFMPEG_NOT_AVAILABLE = "ffmpeg_not_available"
    CONVERSION_FAILED = "conversion_failed"
    CONVERSION_INVALID_OUTPUT = "conversion_invalid_output"
    CONVERSION_CANCELLED = "conversion_cancelled"
    UNSUPPORTED_INPUT_FORMAT = "unsupported_input_format"
    SOURCE_CHANGED = "source_changed"


class AudioConversionError(RuntimeError):
    def __init__(self, code: ConversionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    size: int
    modified_ns: int
    sha256: str


@dataclass(slots=True)
class PreparedYandexAudio:
    """One direct/converted upload input with deterministic cleanup semantics."""

    source_path: Path
    upload_path: Path
    source_format: str
    upload_format: str = "mp3"
    conversion_required: bool = False
    _work_dir: Path | None = None

    def cleanup(self) -> None:
        if self._work_dir is not None:
            shutil.rmtree(self._work_dir, ignore_errors=True)
            self._work_dir = None

    def __enter__(self) -> "PreparedYandexAudio":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.cleanup()


class YandexMp3Profile:
    """Central encoder policy; no UI-controlled codec parameters."""

    encoder = "libmp3lame"

    @classmethod
    def arguments(cls, source: AudioTechnicalInfo, capability: AudioFormatCapabilities) -> list[str]:
        args = ["-c:a", cls.encoder]
        if capability.lossless:
            # High-quality LAME VBR for lossless sources. FFmpeg keeps the input
            # sample rate when the encoder supports it and negotiates only when it
            # must; MusicArk never requests upsampling.
            args += ["-q:a", "2"]
        elif source.bitrate:
            # A lossy source is not assigned a higher target bitrate by policy.
            kbps = max(8, min(256, int(source.bitrate // 1000)))
            args += ["-b:a", f"{kbps}k"]
        else:
            args += ["-q:a", "3"]
        if source.channels and source.channels > 2:
            args += ["-ac", "2"]
        return args


class YandexAudioConversionService:
    """Convert supported non-MP3 sources into validated, temporary MP3 files."""

    ORPHAN_MAX_AGE_SECONDS = 24 * 60 * 60
    DURATION_TOLERANCE_SECONDS = 1.0

    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        locator: FFmpegLocator | None = None,
        adapters: MetadataAdapterRegistry | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        root = (base_dir.resolve() if base_dir is not None else Path.home().resolve())
        self._temp_root = root / ".musicark" / "temp" / "yandex-upload"
        self._temp_root.mkdir(parents=True, exist_ok=True)
        self._locator = locator or FFmpegLocator()
        self._adapters = adapters or MetadataAdapterRegistry()
        self._mp3 = Mp3MetadataAdapter()
        self._timeout_seconds = max(5.0, float(timeout_seconds))
        self.cleanup_orphans()

    @property
    def temp_root(self) -> Path:
        return self._temp_root

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _identity(cls, path: Path) -> SourceIdentity:
        stat = path.stat()
        modified_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        return SourceIdentity(int(stat.st_size), modified_ns, cls._sha256(path))

    @staticmethod
    def _same_source(path: Path, before: SourceIdentity) -> bool:
        if not path.is_file():
            return False
        stat = path.stat()
        modified_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        if int(stat.st_size) != before.size or modified_ns != before.modified_ns:
            return False
        return YandexAudioConversionService._sha256(path) == before.sha256

    def cleanup_orphans(self) -> None:
        now = time.time()
        try:
            candidates = list(self._temp_root.iterdir())
        except OSError:
            return
        for candidate in candidates:
            if not candidate.is_dir() or not candidate.name.startswith("upload-"):
                continue
            try:
                age = now - candidate.stat().st_mtime
            except OSError:
                continue
            if age >= self.ORPHAN_MAX_AGE_SECONDS:
                shutil.rmtree(candidate, ignore_errors=True)

    @staticmethod
    def _metadata_changes(fields: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "title", "artists", "album", "albumArtists", "trackNumber", "totalTracks",
            "discNumber", "totalDiscs", "releaseDate", "year", "genres", "composer",
            "comment", "lyrics",
        }
        return {key: value for key, value in fields.items() if key in allowed and value not in (None, [], "")}

    def _copy_metadata(self, source: Path, output: Path) -> None:
        adapter = self._adapters.adapter_for(source)
        if adapter is None:
            return
        parsed = adapter.read(source)
        artwork = None
        try:
            artwork = adapter.artwork(source)
        except Exception:  # noqa: BLE001 - artwork is optional; audio conversion remains usable
            artwork = None
        self._mp3.apply(
            output,
            self._metadata_changes(dict(parsed.get("fields") or {})),
            artwork_data=artwork[0] if artwork else None,
            artwork_mime=artwork[1] if artwork else None,
        )

    def _validate_output(
        self,
        *,
        source: Path,
        output: Path,
        source_info: AudioTechnicalInfo,
        work_dir: Path,
    ) -> None:
        resolved_output = output.resolve(strict=False)
        resolved_root = self._temp_root.resolve(strict=False)
        if not resolved_output.is_relative_to(resolved_root) or not resolved_output.is_relative_to(work_dir.resolve(strict=False)):
            raise AudioConversionError(
                ConversionErrorCode.CONVERSION_INVALID_OUTPUT,
                "Converted audio escaped the MusicArk temporary namespace.",
            )
        if not output.is_file() or output.stat().st_size <= 0:
            raise AudioConversionError(
                ConversionErrorCode.CONVERSION_INVALID_OUTPUT,
                "FFmpeg did not produce a usable MP3 file.",
            )
        try:
            from mutagen.mp3 import MP3

            converted = MP3(str(output))
            duration = float(converted.info.length)
        except Exception as exc:  # noqa: BLE001
            raise AudioConversionError(
                ConversionErrorCode.CONVERSION_INVALID_OUTPUT,
                "Converted output is not a readable MP3.",
            ) from exc
        if source_info.duration_seconds is not None:
            tolerance = max(
                self.DURATION_TOLERANCE_SECONDS,
                float(source_info.duration_seconds) * 0.02,
            )
            if abs(duration - float(source_info.duration_seconds)) > tolerance:
                raise AudioConversionError(
                    ConversionErrorCode.CONVERSION_INVALID_OUTPUT,
                    "Converted MP3 duration differs unexpectedly from the source.",
                )
        # Ensure normalized tags remain readable after the explicit metadata copy.
        self._mp3.read(output)

    def prepare(self, source: Path) -> PreparedYandexAudio:
        source = source.expanduser().resolve(strict=False)
        capability = capabilities_for_path(source)
        if capability is None or not source.is_file():
            raise AudioConversionError(
                ConversionErrorCode.UNSUPPORTED_INPUT_FORMAT,
                "The selected local audio format is not supported.",
            )
        if capability.can_upload_directly:
            return PreparedYandexAudio(
                source_path=source,
                upload_path=source,
                source_format=capability.format,
                conversion_required=False,
            )
        if not capability.can_transcode_for_yandex:
            raise AudioConversionError(
                ConversionErrorCode.UNSUPPORTED_INPUT_FORMAT,
                "The selected audio format cannot be converted safely for Yandex upload.",
            )

        before = self._identity(source)
        try:
            source_info = probe_audio(source)
        except Exception as exc:  # noqa: BLE001
            raise AudioConversionError(
                ConversionErrorCode.CONVERSION_FAILED,
                "The source audio file cannot be decoded safely.",
            ) from exc

        resolution = self._locator.resolve()
        if not resolution.available or resolution.executable is None:
            code = (
                ConversionErrorCode.FFMPEG_NOT_AVAILABLE
                if resolution.status in {
                    FFmpegStatus.NOT_FOUND,
                    FFmpegStatus.INVALID_BINARY,
                    FFmpegStatus.UNSUPPORTED_VERSION,
                    FFmpegStatus.EXECUTION_FAILED,
                }
                else ConversionErrorCode.CONVERSION_FAILED
            )
            raise AudioConversionError(code, "A supported FFmpeg executable is not available.")

        work_dir = Path(tempfile.mkdtemp(prefix="upload-", dir=str(self._temp_root))).resolve()
        partial = work_dir / "audio.part.mp3"
        final = work_dir / "audio.mp3"
        try:
            runner = FFmpegRunner(resolution.executable)
            arguments = [
                "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(source),
                "-map", "0:a:0",
                "-map_metadata", "-1",
                "-vn",
                *YandexMp3Profile.arguments(source_info, capability),
                "-f", "mp3",
                str(partial),
            ]
            result = runner.run(arguments, timeout_seconds=self._timeout_seconds)
            if result.timed_out:
                raise AudioConversionError(
                    ConversionErrorCode.CONVERSION_CANCELLED,
                    "FFmpeg conversion exceeded the bounded execution time.",
                )
            if result.return_code != 0:
                raise AudioConversionError(
                    ConversionErrorCode.CONVERSION_FAILED,
                    "FFmpeg could not convert the source audio file.",
                )
            self._copy_metadata(source, partial)
            self._validate_output(
                source=source,
                output=partial,
                source_info=source_info,
                work_dir=work_dir,
            )
            os.replace(partial, final)
            self._validate_output(
                source=source,
                output=final,
                source_info=source_info,
                work_dir=work_dir,
            )
            if not self._same_source(source, before):
                raise AudioConversionError(
                    ConversionErrorCode.SOURCE_CHANGED,
                    "The source file changed during conversion; upload was aborted.",
                )
            return PreparedYandexAudio(
                source_path=source,
                upload_path=final,
                source_format=capability.format,
                conversion_required=True,
                _work_dir=work_dir,
            )
        except Exception:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise
