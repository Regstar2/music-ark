"""Narrow, testable FFmpeg infrastructure boundary.

FFmpeg is used only for local audio conversion. Callers never build shell
commands and never depend on human-readable stderr text for domain decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable


FFMPEG_PATH_ENV = "MUSICARK_FFMPEG_PATH"
_MAX_DIAGNOSTIC_CHARS = 16_384
_MIN_SUPPORTED_MAJOR = 5
_VERSION_RE = re.compile(r"ffmpeg version\s+(?:n)?(?P<major>\d+)", re.IGNORECASE)


class FFmpegStatus(str, Enum):
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    INVALID_BINARY = "invalid_binary"
    UNSUPPORTED_VERSION = "unsupported_version"
    EXECUTION_FAILED = "execution_failed"


@dataclass(frozen=True, slots=True)
class FFmpegResolution:
    status: FFmpegStatus
    executable: Path | None = None
    version_line: str | None = None
    source: str | None = None

    @property
    def available(self) -> bool:
        return self.status == FFmpegStatus.AVAILABLE and self.executable is not None


@dataclass(frozen=True, slots=True)
class FFmpegProcessResult:
    return_code: int
    stderr: str
    timed_out: bool = False


class FFmpegLocator:
    """Resolve explicit override -> packaged imageio-ffmpeg -> system PATH."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = max(0.5, float(timeout_seconds))

    @staticmethod
    def _packaged_candidate() -> Path | None:
        try:
            import imageio_ffmpeg

            value = Path(imageio_ffmpeg.get_ffmpeg_exe()).expanduser().resolve(strict=False)
        except Exception:  # noqa: BLE001 - optional resolution path
            return None
        return value if value.is_file() else None

    @staticmethod
    def _path_candidate() -> Path | None:
        value = shutil.which("ffmpeg")
        if not value:
            return None
        return Path(value).expanduser().resolve(strict=False)

    def _validate(self, candidate: Path, *, source: str) -> FFmpegResolution:
        path = candidate.expanduser().resolve(strict=False)
        if not path.is_file():
            return FFmpegResolution(FFmpegStatus.INVALID_BINARY, source=source)
        try:
            completed = subprocess.run(
                [str(path), "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                shell=False,
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return FFmpegResolution(FFmpegStatus.EXECUTION_FAILED, source=source)
        except OSError:
            return FFmpegResolution(FFmpegStatus.INVALID_BINARY, source=source)
        output = (completed.stdout or "")[:_MAX_DIAGNOSTIC_CHARS]
        first_line = output.splitlines()[0].strip() if output.splitlines() else ""
        if completed.returncode != 0 or "ffmpeg version" not in output.casefold():
            return FFmpegResolution(FFmpegStatus.INVALID_BINARY, source=source)
        match = _VERSION_RE.search(output)
        if match is not None and int(match.group("major")) < _MIN_SUPPORTED_MAJOR:
            return FFmpegResolution(
                FFmpegStatus.UNSUPPORTED_VERSION,
                executable=path,
                version_line=first_line or None,
                source=source,
            )
        return FFmpegResolution(
            FFmpegStatus.AVAILABLE,
            executable=path,
            version_line=first_line or None,
            source=source,
        )

    def resolve(self) -> FFmpegResolution:
        override = str(os.getenv(FFMPEG_PATH_ENV, "") or "").strip()
        if override:
            result = self._validate(Path(override), source="explicit")
            # An explicit override is authoritative and fails closed rather than
            # silently switching to another binary.
            return result

        packaged = self._packaged_candidate()
        if packaged is not None:
            result = self._validate(packaged, source="packaged")
            if result.available:
                return result

        system = self._path_candidate()
        if system is not None:
            return self._validate(system, source="path")
        return FFmpegResolution(FFmpegStatus.NOT_FOUND)


class FFmpegRunner:
    """Execute one already-validated absolute FFmpeg path without a shell."""

    def __init__(self, executable: Path) -> None:
        resolved = executable.expanduser().resolve(strict=False)
        if not resolved.is_absolute() or not resolved.is_file():
            raise ValueError("FFmpeg executable must be an existing absolute file.")
        self._executable = resolved

    @property
    def executable(self) -> Path:
        return self._executable

    def run(self, arguments: Iterable[str], *, timeout_seconds: float = 300.0) -> FFmpegProcessResult:
        command = [str(self._executable), *[str(value) for value in arguments]]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                shell=False,
                timeout=max(1.0, float(timeout_seconds)),
                check=False,
                cwd=str(self._executable.parent),
            )
        except subprocess.TimeoutExpired as exc:
            stderr = str(exc.stderr or "")[-_MAX_DIAGNOSTIC_CHARS:]
            return FFmpegProcessResult(-1, stderr, timed_out=True)
        except OSError as exc:
            return FFmpegProcessResult(-1, exc.__class__.__name__, timed_out=False)
        return FFmpegProcessResult(
            int(completed.returncode),
            (completed.stderr or "")[-_MAX_DIAGNOSTIC_CHARS:],
            timed_out=False,
        )
