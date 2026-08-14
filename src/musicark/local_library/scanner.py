"""Incremental recursive scanner for MusicArk v0.4 local libraries."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import stat

from .metadata_reader import LocalMetadataReader
from .models import LocalAudioRecord, LocalLibraryRoot, LocalScanResult
from musicark.storage.local_library_storage import (
    LocalLibraryStorageRepository,
    normalize_local_path,
)

SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        result = path.stat(follow_symlinks=False)
    except OSError:
        return True
    attributes = getattr(result, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


class LocalLibraryScanner:
    def __init__(
        self,
        repository: LocalLibraryStorageRepository,
        metadata_reader: LocalMetadataReader | None = None,
    ) -> None:
        self._repository = repository
        self._metadata_reader = metadata_reader or LocalMetadataReader()

    def scan(self, root: LocalLibraryRoot) -> LocalScanResult:
        root_path = Path(root.path)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Local library root is not an accessible directory: {root.path}")

        existing = self._repository.file_states(root.id)
        seen: set[str] = set()
        upserts: list[LocalAudioRecord] = []
        result = LocalScanResult()
        walk_failed = False

        def on_walk_error(error: OSError) -> None:
            nonlocal walk_failed
            walk_failed = True
            result.errors += 1
            if len(result.error_items) < 100:
                result.error_items.append(
                    {"path": str(getattr(error, "filename", root.path) or root.path), "error": str(error)}
                )

        for current, dir_names, file_names in os.walk(
            root_path,
            topdown=True,
            followlinks=False,
            onerror=on_walk_error,
        ):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for name in dir_names:
                candidate = current_path / name
                if not _is_reparse_or_symlink(candidate):
                    kept_dirs.append(name)
            dir_names[:] = kept_dirs

            for file_name in file_names:
                path = current_path / file_name
                if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                    continue
                if file_name.startswith("~$") or path.is_symlink():
                    continue
                try:
                    info = path.stat()
                except OSError as exc:
                    self._record_error(result, path, exc)
                    continue

                normalized = normalize_local_path(path)
                seen.add(normalized)
                result.scanned_files += 1
                old = existing.get(normalized)
                modified_ns = int(getattr(info, "st_mtime_ns", int(info.st_mtime * 1_000_000_000)))
                if (
                    old is not None
                    and int(old["file_size"]) == int(info.st_size)
                    and int(old.get("modified_ns") or 0) == modified_ns
                ):
                    result.unchanged += 1
                    continue

                try:
                    metadata = self._metadata_reader.read(path)
                except Exception as exc:  # noqa: BLE001 - one bad file cannot abort the scan.
                    self._record_error(result, path, exc)
                    continue

                upserts.append(
                    LocalAudioRecord(
                        library_root_id=root.id,
                        path=str(path.resolve(strict=False)),
                        normalized_path=normalized,
                        file_name=path.name,
                        extension=path.suffix.lower(),
                        file_size=int(info.st_size),
                        modified_ns=modified_ns,
                        metadata=metadata,
                        sha256="",
                    )
                )
                if old is None:
                    result.added += 1
                else:
                    result.updated += 1

        result.removed = self._repository.apply_scan(
            root.id,
            upserts=upserts,
            seen_normalized_paths=seen,
            scanned_at=_utc_now(),
            allow_removals=not walk_failed,
        )
        return result

    @staticmethod
    def _record_error(result: LocalScanResult, path: Path, error: Exception) -> None:
        result.errors += 1
        if len(result.error_items) < 100:
            result.error_items.append({"path": str(path), "error": str(error)})
