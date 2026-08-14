"""Application orchestration for MusicArk v0.4 local music libraries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.core.config import load_config
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from .models import LocalLibraryRoot
from .scanner import LocalLibraryScanner


def _root_payload(root: LocalLibraryRoot) -> dict[str, Any]:
    return {
        "id": root.id,
        "path": root.path,
        "normalizedPath": root.normalized_path,
        "enabled": root.enabled,
        "createdAt": root.created_at,
        "lastScannedAt": root.last_scanned_at,
    }


class LocalLibraryService:
    def __init__(
        self,
        base_dir: Path | None = None,
        repository: LocalLibraryStorageRepository | None = None,
        scanner: LocalLibraryScanner | None = None,
    ) -> None:
        self._base_dir = base_dir
        database_path = self._resolve_database_path()
        initialize_database(database_path)
        self._repository = repository or LocalLibraryStorageRepository(database_path)
        self._scanner = scanner or LocalLibraryScanner(self._repository)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def roots(self) -> dict[str, Any]:
        items = [_root_payload(root) for root in self._repository.list_roots()]
        return {"count": len(items), "items": items}

    def add_root(self, path: str) -> dict[str, Any]:
        root = self._repository.add_root(Path(path))
        return {"root": _root_payload(root), "roots": self.roots()}

    def remove_root(self, root_id: int) -> dict[str, Any]:
        removed = self._repository.remove_root(root_id)
        return {"removed": removed, "roots": self.roots()}

    def scan(self, root_id: int | None = None) -> dict[str, Any]:
        roots = self._repository.list_roots()
        if root_id is not None:
            roots = [root for root in roots if root.id == root_id]
            if not roots:
                raise ValueError(f"Local library root {root_id} was not found.")
        roots = [root for root in roots if root.enabled]

        total = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0, "errors": 0, "scanned": 0}
        errors: list[dict[str, str]] = []
        per_root: list[dict[str, Any]] = []
        for root in roots:
            try:
                result = self._scanner.scan(root)
            except ValueError as exc:
                error = {"path": root.path, "error": str(exc)}
                total["errors"] += 1
                if len(errors) < 100:
                    errors.append(error)
                per_root.append(
                    {
                        "rootId": root.id,
                        "path": root.path,
                        "added": 0,
                        "updated": 0,
                        "removed": 0,
                        "unchanged": 0,
                        "errors": 1,
                        "scanned": 0,
                        "errorItems": [error],
                    }
                )
                continue

            data = result.as_dict()
            per_root.append({"rootId": root.id, "path": root.path, **data})
            for key in total:
                total[key] += int(data.get(key, 0))
            for item in data.get("errorItems", []):
                if len(errors) < 100:
                    errors.append(dict(item))
        return {**total, "errorItems": errors, "roots": per_root, "stats": self.stats()}

    def tracks(
        self,
        *,
        limit: int = 500,
        offset: int = 0,
        search: str = "",
        sort: str = "artist",
        root_id: int | None = None,
    ) -> dict[str, Any]:
        page_limit = max(1, min(int(limit), 5000))
        page_offset = max(0, int(offset))
        items, total = self._repository.list_tracks(
            limit=page_limit,
            offset=page_offset,
            search=search,
            sort=sort,
            root_id=root_id,
        )
        return {
            "count": total,
            "limit": page_limit,
            "offset": page_offset,
            "items": items,
        }

    def track(self, track_id: int) -> dict[str, Any]:
        item = self._repository.get_track(track_id)
        if item is None:
            raise ValueError(f"Local track {track_id} was not found.")
        return {"track": item}

    def stats(self) -> dict[str, Any]:
        return self._repository.local_stats()
