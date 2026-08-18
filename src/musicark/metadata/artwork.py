"""Artwork extraction/cache used by Local Library and the metadata editor."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import struct
from typing import Any

from .formats.mp3 import Mp3MetadataAdapter
from .models import ArtworkInfo


_MAX_ARTWORK_BYTES = 8 * 1024 * 1024


def _image_dimensions(data: bytes, mime: str) -> tuple[int | None, int | None]:
    """Read JPEG/PNG dimensions without introducing an image-processing dependency."""
    if mime == "image/png" and len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if mime in {"image/jpeg", "image/jpg"} and data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            segment = int.from_bytes(data[index:index + 2], "big")
            if segment < 2 or index + segment > len(data):
                break
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                if index + 7 <= len(data):
                    height = int.from_bytes(data[index + 3:index + 5], "big")
                    width = int.from_bytes(data[index + 5:index + 7], "big")
                    return width, height
                break
            index += segment
    return None, None


def _normalized_mime(mime: str | None, data: bytes) -> str:
    value = str(mime or "").split(";", 1)[0].strip().casefold()
    if value in {"image/jpeg", "image/jpg"}:
        return "image/jpeg"
    if value == "image/png":
        return value
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return value if value.startswith("image/") else "application/octet-stream"


class ArtworkCache:
    """Disk-backed cache; the Local Library receives paths, never base64 image data."""

    def __init__(self, database_path: Path, base_dir: Path | None) -> None:
        self._database_path = database_path
        root = base_dir.resolve() if base_dir is not None else database_path.resolve().parent
        self._root = root / ".musicark" / "artwork"
        self._local = self._root / "local"
        self._yandex = self._root / "yandex"
        self._local.mkdir(parents=True, exist_ok=True)
        self._yandex.mkdir(parents=True, exist_ok=True)
        self._mp3 = Mp3MetadataAdapter()

    @staticmethod
    def _fingerprint(path: Path, source_external_id: str | None = None) -> str:
        stat = path.stat()
        modified_ns = int(
            getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
        )
        return f"{int(stat.st_size)}:{modified_ns}:{source_external_id or ''}"

    @staticmethod
    def _info_from_cache_row(
        row: tuple[Any, ...] | None,
        fingerprint: str,
    ) -> ArtworkInfo | None:
        if row is None or str(row[6] or "") != fingerprint:
            return None
        source = str(row[1] or "cache")
        if source == "none":
            return ArtworkInfo(source="none")
        cache_path = str(row[0] or "")
        if not cache_path or not Path(cache_path).is_file():
            return None
        return ArtworkInfo(
            present=True,
            cache_path=cache_path,
            source=source,
            mime=row[2],
            width=row[3],
            height=row[4],
            byte_size=row[5],
        )

    def _cached(self, local_file_id: int, fingerprint: str) -> ArtworkInfo | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT cache_path, source, mime, width, height, byte_size, fingerprint
                    FROM local_artwork_cache WHERE local_file_id=?
                    """,
                    (int(local_file_id),),
                ).fetchone()
        except sqlite3.Error:
            return None
        return self._info_from_cache_row(row, fingerprint)

    def _cached_batch(self, local_file_ids: list[int]) -> dict[int, tuple[Any, ...]]:
        if not local_file_ids:
            return {}
        placeholders = ",".join("?" for _ in local_file_ids)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    f"""
                    SELECT local_file_id, cache_path, source, mime, width, height,
                           byte_size, fingerprint
                    FROM local_artwork_cache
                    WHERE local_file_id IN ({placeholders})
                    """,
                    local_file_ids,
                ).fetchall()
        except sqlite3.Error:
            return {}
        return {
            int(row[0]): (
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
            )
            for row in rows
        }

    def _store_local(
        self,
        local_file_id: int,
        fingerprint: str,
        data: bytes,
        mime: str,
        *,
        source: str,
    ) -> ArtworkInfo:
        if not data or len(data) > _MAX_ARTWORK_BYTES:
            return ArtworkInfo()
        normalized_mime = _normalized_mime(mime, data)
        suffix = ".png" if normalized_mime == "image/png" else ".jpg"
        for stale in self._local.glob(f"{int(local_file_id)}.*"):
            try:
                stale.unlink()
            except OSError:
                pass
        path = self._local / f"{int(local_file_id)}{suffix}"
        path.write_bytes(data)
        width, height = _image_dimensions(data, normalized_mime)
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO local_artwork_cache(
                        local_file_id, fingerprint, cache_path, source, mime,
                        width, height, byte_size, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(local_file_id) DO UPDATE SET
                        fingerprint=excluded.fingerprint,
                        cache_path=excluded.cache_path,
                        source=excluded.source,
                        mime=excluded.mime,
                        width=excluded.width,
                        height=excluded.height,
                        byte_size=excluded.byte_size,
                        updated_at=datetime('now')
                    """,
                    (
                        int(local_file_id),
                        fingerprint,
                        str(path.resolve()),
                        source,
                        normalized_mime,
                        width,
                        height,
                        len(data),
                    ),
                )
        return ArtworkInfo(
            True,
            str(path.resolve()),
            normalized_mime,
            width,
            height,
            len(data),
            source,
        )

    def _store_absent(self, local_file_id: int, fingerprint: str) -> ArtworkInfo:
        for stale in self._local.glob(f"{int(local_file_id)}.*"):
            try:
                stale.unlink()
            except OSError:
                pass
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO local_artwork_cache(
                            local_file_id, fingerprint, cache_path, source, mime,
                            width, height, byte_size, updated_at
                        ) VALUES (?, ?, '', 'none', NULL, NULL, NULL, NULL, datetime('now'))
                        ON CONFLICT(local_file_id) DO UPDATE SET
                            fingerprint=excluded.fingerprint,
                            cache_path='',
                            source='none',
                            mime=NULL,
                            width=NULL,
                            height=NULL,
                            byte_size=NULL,
                            updated_at=datetime('now')
                        """,
                        (int(local_file_id), fingerprint),
                    )
        except sqlite3.Error:
            return ArtworkInfo()
        return ArtworkInfo(source="none")

    def _clear_local(self, local_file_id: int) -> None:
        for stale in self._local.glob(f"{int(local_file_id)}.*"):
            try:
                stale.unlink()
            except OSError:
                pass
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        "DELETE FROM local_artwork_cache WHERE local_file_id=?",
                        (int(local_file_id),),
                    )
        except sqlite3.Error:
            pass

    def cache_yandex(self, external_id: str, data: bytes, mime: str) -> str | None:
        if not data or len(data) > _MAX_ARTWORK_BYTES:
            return None
        normalized = _normalized_mime(mime, data)
        suffix = ".png" if normalized == "image/png" else ".jpg"
        safe_id = "".join(
            char for char in str(external_id) if char.isalnum() or char in "-_"
        )
        if not safe_id:
            return None
        path = self._yandex / f"{safe_id}{suffix}"
        path.write_bytes(data)
        return str(path.resolve())

    def yandex_cached(self, external_id: str) -> str | None:
        safe_id = "".join(
            char for char in str(external_id) if char.isalnum() or char in "-_"
        )
        for suffix in (".jpg", ".png"):
            path = self._yandex / f"{safe_id}{suffix}"
            if path.is_file():
                return str(path.resolve())
        return None

    def _ensure_uncached(
        self,
        local_file_id: int,
        path: Path,
        fingerprint: str,
        *,
        source_external_id: str | None,
    ) -> ArtworkInfo:
        embedded: tuple[bytes, str] | None = None
        if path.suffix.casefold() == ".mp3":
            try:
                embedded = self._mp3.artwork(path)
            except Exception:  # noqa: BLE001 - artwork is optional for Local Library rows.
                embedded = None
        if embedded is not None:
            return self._store_local(
                local_file_id,
                fingerprint,
                embedded[0],
                embedded[1],
                source="embedded",
            )

        # A confirmed Yandex identity may reuse artwork that an explicit search/import
        # already cached. Never perform a background Yandex request for a library row.
        if source_external_id:
            yandex_path = self.yandex_cached(source_external_id)
            if yandex_path:
                data = Path(yandex_path).read_bytes()
                mime = (
                    "image/png"
                    if yandex_path.casefold().endswith(".png")
                    else "image/jpeg"
                )
                return self._store_local(
                    local_file_id,
                    fingerprint,
                    data,
                    mime,
                    source="yandex_identity_cache",
                )

        # Cache the negative result too. Large libraries commonly contain many
        # files without embedded artwork; reparsing those tags on every page load
        # is pure repeated work until the file or provider identity changes.
        return self._store_absent(local_file_id, fingerprint)

    def ensure_local(
        self,
        local_file_id: int,
        path: Path,
        *,
        source_external_id: str | None = None,
    ) -> ArtworkInfo:
        fingerprint = self._fingerprint(path, source_external_id)
        cached = self._cached(local_file_id, fingerprint)
        if cached is not None:
            if (
                not cached.present
                and source_external_id
                and self.yandex_cached(source_external_id)
            ):
                cached = None
            else:
                return cached
        return self._ensure_uncached(
            local_file_id,
            path,
            fingerprint,
            source_external_id=source_external_id,
        )

    def batch(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        ids = [int(row["id"]) for row in rows]
        cached_rows = self._cached_batch(ids)
        for row in rows:
            file_id = int(row["id"])
            path = Path(str(row["path"]))
            source_external_id = (
                str(row.get("source_external_id"))
                if row.get("source_external_id")
                else None
            )
            if not path.is_file():
                result[str(file_id)] = ArtworkInfo().as_dict()
                continue
            try:
                fingerprint = self._fingerprint(path, source_external_id)
            except OSError:
                result[str(file_id)] = ArtworkInfo().as_dict()
                continue
            info = self._info_from_cache_row(cached_rows.get(file_id), fingerprint)
            if info is not None:
                if (
                    not info.present
                    and source_external_id
                    and self.yandex_cached(source_external_id)
                ):
                    info = None
                else:
                    result[str(file_id)] = info.as_dict()
                    continue
            info = self._ensure_uncached(
                file_id,
                path,
                fingerprint,
                source_external_id=source_external_id,
            )
            result[str(file_id)] = info.as_dict()
        return result
