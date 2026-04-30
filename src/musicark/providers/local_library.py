"""Local library scanning provider for v0.4."""

from __future__ import annotations

import hashlib
from pathlib import Path
import wave

from musicark.core.errors import MusicArkError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository

from .base import MusicProvider
from .models import (
    LocalAudioFile,
    ProviderCapabilities,
    ProviderPlaylist,
    ProviderTrack,
    TrackSource,
)


AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav"}


class LocalLibraryError(MusicArkError):
    """Raised when local library scan fails."""


class LocalLibraryProvider(MusicProvider):
    """Provider that scans local folders and stores local audio file records."""

    @property
    def provider_id(self) -> str:
        return "local_library"

    @property
    def display_name(self) -> str:
        return "Local Library"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_authenticate=False,
            can_scan_library=True,
            can_scan_playlists=False,
            can_download_tracks=False,
            can_upload_tracks=False,
            can_create_playlists=False,
            can_edit_playlists=False,
            supports_track_availability=True,
            supports_user_uploads=True,
        )

    def health_check(self) -> dict[str, str]:
        return {"status": "ok", "provider": "local_library"}

    def list_tracks(self) -> list[ProviderTrack]:
        return []

    def list_playlists(self) -> list[ProviderPlaylist]:
        return []

    def scan(self, root_path: Path, database_path: Path) -> dict:
        if not root_path.exists() or not root_path.is_dir():
            raise LocalLibraryError(f"Scan path '{root_path}' is not a directory.")

        storage = LocalLibraryStorageRepository(database_path)
        audit = AuditLogRepository(database_path)

        indexed = 0
        skipped = 0
        failed = 0
        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            try:
                local_audio = build_local_audio_file(file_path)
                storage.upsert_local_audio_file(local_audio)
                track_source = TrackSource(
                    track_id=f"local:{local_audio.sha256}",
                    source_type="local_file",
                    provider_id="local_library",
                    external_id=local_audio.path,
                    url=str(file_path.resolve()),
                    availability="available",
                    raw_data={"path": local_audio.path},
                )
                storage.upsert_track_source(track_source)
                indexed += 1
            except Exception:  # noqa: BLE001
                failed += 1

        audit.append(
            AuditEvent(
                event_type="local_scan",
                entity_type="provider",
                entity_id="local_library",
                status="success",
                details=f"path={root_path} indexed={indexed} skipped={skipped} failed={failed}",
            )
        )
        return {
            "provider": "local_library",
            "path": str(root_path),
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
        }


def calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_basic_metadata(file_path: Path) -> tuple[float | None, dict]:
    duration: float | None = None
    metadata: dict = {}

    if file_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(file_path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate) if rate else None
                metadata = {
                    "channels": wav_file.getnchannels(),
                    "sample_width": wav_file.getsampwidth(),
                    "frame_rate": rate,
                }
                return duration, metadata
        except Exception:  # noqa: BLE001
            pass

    try:
        from mutagen import File as MutagenFile  # type: ignore

        audio = MutagenFile(str(file_path))
        if audio is not None and getattr(audio, "info", None) is not None:
            info = audio.info
            duration = float(getattr(info, "length", 0.0)) or None
        tags = getattr(audio, "tags", None)
        if tags:
            metadata = {str(key): str(value) for key, value in tags.items()}
    except Exception:  # noqa: BLE001
        metadata = {}

    return duration, metadata


def build_local_audio_file(file_path: Path) -> LocalAudioFile:
    """Build LocalAudioFile from file path with stable hash and basic metadata."""
    resolved = file_path.resolve()
    duration, metadata = _extract_basic_metadata(resolved)
    return LocalAudioFile(
        path=str(resolved),
        sha256=calculate_sha256(resolved),
        file_size=resolved.stat().st_size,
        duration_seconds=duration,
        codec=resolved.suffix.lower().lstrip("."),
        metadata_json=metadata,
    )
