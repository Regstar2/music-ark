"""Resolve and acquire trusted local reference audio for a provider track identity."""

from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import sqlite3

from musicark.credentials import SystemCredentialStore
from musicark.download.models import DownloadTask
from musicark.download.provider import DownloadProviderError, YandexMusicDownloadProvider

from .models import ReferenceAudio


_YANDEX_REFERENCE = re.compile(r"^yandex[_-](?P<id>\d+)$", re.IGNORECASE)
_AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"})


class ReferenceAcquisitionError(RuntimeError):
    """Raised when an exact provider reference cannot be acquired safely."""


def strict_yandex_id_from_path(path: Path) -> str | None:
    """Return an ID only for the exact historical yandex_<id>/yandex-<id> convention."""
    match = _YANDEX_REFERENCE.fullmatch(path.stem)
    return match.group("id") if match else None


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8", "surrogatepass")
    return sha256(payload).hexdigest()


def reference_root(database_path: Path, base_dir: Path | None = None) -> Path:
    app_root = base_dir or database_path.parent.parent
    return app_root / ".musicark" / "downloads" / "yandex"


class ReferenceAudioResolver:
    def __init__(self, database_path: Path, base_dir: Path | None = None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir

    def resolve(self, provider_id: str, external_id: str) -> ReferenceAudio | None:
        if provider_id != "yandex_music" or not str(external_id).isdigit():
            return None
        expected = str(external_id)

        # Prefer the app-managed reference cache when present.
        root = reference_root(self._database_path, self._base_dir)
        if root.is_dir():
            for prefix in ("yandex_", "yandex-"):
                for ext in sorted(_AUDIO_EXTENSIONS):
                    candidate = root / f"{prefix}{expected}{ext}"
                    if candidate.is_file() and candidate.stat().st_size > 0:
                        return ReferenceAudio(candidate, provider_id, expected)

        # Also allow already indexed local files, but only the same strict filename convention.
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT path FROM local_audio_files WHERE availability != 'missing' ORDER BY id"
                ).fetchall()
        except sqlite3.Error:
            return None
        for (raw_path,) in rows:
            path = Path(str(raw_path))
            if path.suffix.casefold() not in _AUDIO_EXTENSIONS:
                continue
            if strict_yandex_id_from_path(path) == expected and path.is_file() and path.stat().st_size > 0:
                return ReferenceAudio(path, provider_id, expected)
        return None


class ReferenceAudioAcquirer:
    """Acquire one exact Yandex reference into MusicArk's private cache on demand.

    The downloaded reference is deliberately not inserted into Local Library: it is
    analysis input, not user-owned library content, and must not affect identity matching.
    """

    def __init__(self, database_path: Path, base_dir: Path | None = None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir

    def acquire(self, provider_id: str, external_id: str) -> ReferenceAudio:
        expected = str(external_id).strip()
        if provider_id != "yandex_music" or not expected.isdigit():
            raise ReferenceAcquisitionError("reference_provider_not_supported")

        token: str | None = None
        try:
            token = SystemCredentialStore().get_token()
        except Exception:  # noqa: BLE001 - provider still has env/local.properties fallback.
            token = None

        provider = YandexMusicDownloadProvider(base_dir=self._base_dir, token=token)
        root = reference_root(self._database_path, self._base_dir)
        task = DownloadTask(
            task_type="variant_reference",
            source_id=expected,
            provider_id=provider.provider_id,
            target_folder=str(root),
            raw_payload={"track_id": expected, "quality": "best"},
        )
        try:
            local_audio = provider.execute(task)
        except Exception as exc:  # provider/auth/network errors remain conservative.
            raise ReferenceAcquisitionError(f"reference_download_failed: {exc}") from exc

        path = Path(local_audio.path)
        if strict_yandex_id_from_path(path) != expected or not path.is_file() or path.stat().st_size <= 0:
            raise ReferenceAcquisitionError("reference_download_invalid")
        return ReferenceAudio(path, provider_id, expected)
