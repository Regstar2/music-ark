"""Chromaprint fingerprinting for Local Library files."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
from typing import Callable
from urllib.parse import urlsplit
import zipfile

import requests


class FingerprintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioFingerprint:
    fingerprint: str
    duration: int

    def as_dict(self) -> dict[str, object]:
        return {"fingerprint": self.fingerprint, "duration": self.duration}


class FpcalcProvisioner:
    """Resolve or install the official Chromaprint fpcalc tool for MusicArk.

    Desktop users should not need to install Chromaprint manually or edit PATH.
    The managed Windows x64 build is downloaded from the official
    acoustid/chromaprint GitHub release, verified against a pinned archive
    SHA-256, and extracted into MusicArk's private tools directory.
    """

    VERSION = "1.6.1"
    WINDOWS_X64_URL = (
        "https://github.com/acoustid/chromaprint/releases/download/"
        "v1.6.1/chromaprint-fpcalc-1.6.1-windows-x86_64.zip"
    )
    WINDOWS_X64_SHA256 = "735d6182b38e9f364b84ce6f4ccd682c75e2851de89735711d6b762d12b92a4e"
    MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
    _ALLOWED_DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com"}

    def __init__(
        self,
        database_path: Path,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        http_get: Callable[..., requests.Response] = requests.get,
    ) -> None:
        self._database_path = database_path
        self._runner = runner
        self._http_get = http_get

    @property
    def install_dir(self) -> Path:
        return self._database_path.parent / "tools" / "chromaprint" / self.VERSION

    @property
    def executable_path(self) -> Path:
        return self.install_dir / "fpcalc.exe"

    @staticmethod
    def _is_windows_x64() -> bool:
        if os.name != "nt":
            return False
        machine = platform.machine().casefold()
        return machine in {"amd64", "x86_64"}

    def _validate_executable(self, path: Path) -> bool:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        try:
            completed = self._runner(
                [str(path), "-version"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def _download_archive(self) -> bytes:
        try:
            response = self._http_get(
                self.WINDOWS_X64_URL,
                stream=True,
                timeout=(6, 60),
                allow_redirects=True,
                headers={"User-Agent": "MusicArk/0.12.0"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise FingerprintError("MusicArk could not download the official Chromaprint fpcalc tool.") from exc

        final_host = (urlsplit(str(response.url)).hostname or "").casefold()
        if final_host not in self._ALLOWED_DOWNLOAD_HOSTS:
            raise FingerprintError("Chromaprint download redirected to an unexpected host.")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.MAX_DOWNLOAD_BYTES:
                    raise FingerprintError("Chromaprint download is unexpectedly large.")
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        digest = hashlib.sha256()
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            total += len(chunk)
            if total > self.MAX_DOWNLOAD_BYTES:
                raise FingerprintError("Chromaprint download exceeded the allowed size.")
            digest.update(chunk)
            chunks.append(chunk)
        if digest.hexdigest().casefold() != self.WINDOWS_X64_SHA256.casefold():
            raise FingerprintError("Chromaprint download failed SHA-256 verification.")
        return b"".join(chunks)

    @staticmethod
    def _fpcalc_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
        matches = [
            info
            for info in archive.infolist()
            if not info.is_dir() and Path(info.filename.replace("\\", "/")).name.casefold() == "fpcalc.exe"
        ]
        if len(matches) != 1:
            raise FingerprintError("Official Chromaprint archive does not contain exactly one fpcalc.exe.")
        return matches[0]

    def install(self) -> str:
        if not self._is_windows_x64():
            raise FingerprintError(
                "Automatic fpcalc provisioning is currently supported on Windows x64 only."
            )

        payload = self._download_archive()
        self.install_dir.mkdir(parents=True, exist_ok=True)
        target = self.executable_path
        temporary = target.with_suffix(".tmp")
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                member = self._fpcalc_member(archive)
                with archive.open(member) as source, temporary.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            temporary.replace(target)
        except (OSError, zipfile.BadZipFile) as exc:
            temporary.unlink(missing_ok=True)
            raise FingerprintError("MusicArk could not install the Chromaprint fpcalc tool.") from exc

        if not self._validate_executable(target):
            target.unlink(missing_ok=True)
            raise FingerprintError("Downloaded Chromaprint fpcalc failed its startup check.")
        return str(target)

    def resolve(self) -> str:
        override = os.getenv("MUSICARK_FPCALC_PATH", "").strip()
        if override:
            candidate = Path(override).expanduser()
            if self._validate_executable(candidate):
                return str(candidate)
            raise FingerprintError("MUSICARK_FPCALC_PATH does not point to a working fpcalc executable.")

        # Prefer the MusicArk-managed copy so normal operation never depends on
        # machine PATH after the first successful provisioning.
        if self._validate_executable(self.executable_path):
            return str(self.executable_path)

        # Keep an existing system install compatible for developers and power users.
        found = shutil.which("fpcalc")
        if found and self._validate_executable(Path(found)):
            return found

        return self.install()


class FingerprintService:
    def __init__(
        self,
        database_path: Path,
        *,
        executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        provisioner: Callable[[], str] | None = None,
    ) -> None:
        self._database_path = database_path
        self._executable = executable
        self._runner = runner
        self._provisioner = provisioner
        self._resolved_executable: str | None = None

    def _resolve_executable(self) -> str:
        if self._executable:
            return self._executable
        if self._resolved_executable:
            return self._resolved_executable
        if self._provisioner is not None:
            resolved = self._provisioner()
        else:
            resolved = FpcalcProvisioner(self._database_path, runner=self._runner).resolve()
        self._resolved_executable = resolved
        return resolved

    @staticmethod
    def _file_key(path: Path) -> str:
        stat = path.stat()
        modified = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        return f"{stat.st_size}:{modified}"

    def fingerprint(self, local_file_id: int, path: Path) -> AudioFingerprint:
        if not path.is_file():
            raise FingerprintError("The indexed audio file is missing.")
        file_key = self._file_key(path)
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                "SELECT file_key, fingerprint, duration_seconds FROM external_audio_fingerprints WHERE local_file_id=?",
                (int(local_file_id),),
            ).fetchone()
        if row and str(row[0]) == file_key:
            return AudioFingerprint(str(row[1]), int(round(float(row[2]))))

        try:
            completed = self._runner(
                [self._resolve_executable(), "-json", str(path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                shell=False,
            )
        except FingerprintError:
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            raise FingerprintError("Chromaprint fpcalc failed to start.") from exc
        if completed.returncode != 0:
            raise FingerprintError("Chromaprint fpcalc failed for the selected file.")
        try:
            payload = json.loads(completed.stdout)
            value = str(payload["fingerprint"]).strip()
            duration = int(round(float(payload["duration"])))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise FingerprintError("Chromaprint fpcalc returned an invalid result.") from exc
        if not value or duration <= 0:
            raise FingerprintError("Chromaprint fpcalc returned an empty fingerprint.")

        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO external_audio_fingerprints(local_file_id, file_key, fingerprint, duration_seconds, updated_at)
                    VALUES(?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(local_file_id) DO UPDATE SET
                        file_key=excluded.file_key,
                        fingerprint=excluded.fingerprint,
                        duration_seconds=excluded.duration_seconds,
                        updated_at=excluded.updated_at
                    """,
                    (int(local_file_id), file_key, value, duration),
                )
        return AudioFingerprint(value, duration)
