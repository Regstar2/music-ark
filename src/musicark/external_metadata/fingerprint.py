"""Chromaprint fingerprinting for Local Library files."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Callable


class FingerprintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioFingerprint:
    fingerprint: str
    duration: int

    def as_dict(self) -> dict[str, object]:
        return {"fingerprint": self.fingerprint, "duration": self.duration}


class FingerprintService:
    def __init__(
        self,
        database_path: Path,
        *,
        executable: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._database_path = database_path
        self._executable = executable
        self._runner = runner

    def _resolve_executable(self) -> str:
        if self._executable:
            return self._executable
        found = shutil.which("fpcalc")
        if not found:
            raise FingerprintError("Chromaprint fpcalc is not installed or not available in PATH.")
        return found

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
