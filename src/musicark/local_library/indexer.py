"""Efficient single-file indexing for files created inside a Local Library root."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from typing import Any

from musicark.storage.local_library_storage import LocalLibraryStorageRepository, normalize_local_path

from .metadata_reader import LocalMetadataReader
from .models import LocalAudioRecord, LocalLibraryRoot
from .scanner import SUPPORTED_AUDIO_EXTENSIONS


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LocalFileIndexer:
    """Index one known file without walking or rescanning the surrounding library."""

    def __init__(
        self,
        database_path: Path,
        repository: LocalLibraryStorageRepository,
        metadata_reader: LocalMetadataReader | None = None,
    ) -> None:
        self._database_path = database_path
        self._repository = repository
        self._metadata_reader = metadata_reader or LocalMetadataReader()

    def index_file(self, path: Path, root: LocalLibraryRoot) -> dict[str, Any]:
        if not root.enabled:
            raise ValueError("The selected Local Library root is disabled.")
        root_path = Path(root.path).expanduser().resolve(strict=False)
        candidate = path.expanduser().resolve(strict=False)
        try:
            candidate.relative_to(root_path)
        except ValueError as exc:
            raise ValueError("Downloaded file is outside the selected Local Library root.") from exc
        if candidate.suffix.casefold() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio extension: {candidate.suffix}")
        if not candidate.is_file():
            raise ValueError(f"Downloaded audio file does not exist: {candidate}")
        info = candidate.stat()
        if info.st_size <= 0:
            raise ValueError("Downloaded audio file is empty.")

        metadata = self._metadata_reader.read(candidate)
        normalized = normalize_local_path(candidate)
        modified_ns = int(getattr(info, "st_mtime_ns", int(info.st_mtime * 1_000_000_000)))
        record = LocalAudioRecord(
            library_root_id=root.id,
            path=str(candidate),
            normalized_path=normalized,
            file_name=candidate.name,
            extension=candidate.suffix.casefold(),
            file_size=int(info.st_size),
            modified_ns=modified_ns,
            metadata=metadata,
            sha256="",
        )
        # Reuse the exact v0.4 structured upsert. allow_removals=False is the key:
        # a single downloaded file must never make unvisited library files disappear.
        self._repository.apply_scan(
            root.id,
            upserts=[record],
            seen_normalized_paths={normalized},
            scanned_at=_now(),
            allow_removals=False,
        )
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                """
                SELECT id, library_root_id, path, title, artists_json, album,
                       duration_seconds, codec, file_size
                FROM local_audio_files WHERE normalized_path=?
                """,
                (normalized,),
            ).fetchone()
        if row is None:
            raise ValueError("Downloaded file was not found after Local Library indexing.")
        return {
            "id": int(row[0]),
            "rootId": int(row[1]),
            "path": str(row[2]),
            "title": row[3],
            "artistsJson": row[4],
            "album": row[5],
            "durationSeconds": row[6],
            "codec": row[7],
            "fileSize": int(row[8] or 0),
        }
