"""Bounded external artwork cache for explicit metadata candidates."""

from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, urlunsplit

from musicark.storage.external_metadata_migration import migrate_external_metadata_v012

from .models import ExternalArtworkCandidate
from .network import ExternalNetworkTransport

_MAX_ARTWORK_BYTES = 8 * 1024 * 1024
_ALLOWED_CAA_IMAGE_HOST_SUFFIXES = ("coverartarchive.org", "archive.org")


class ExternalArtworkCache:
    def __init__(self, database_path: Path, base_dir: Path | None, transport: ExternalNetworkTransport) -> None:
        self._database_path = database_path
        root = base_dir.resolve() if base_dir is not None else database_path.resolve().parent
        self._root = root / ".musicark" / "artwork" / "external"
        self._root.mkdir(parents=True, exist_ok=True)
        self._transport = transport
        with closing(sqlite3.connect(database_path)) as conn:
            with conn:
                migrate_external_metadata_v012(conn)

    @staticmethod
    def _normalize_trusted_url(url: str) -> str | None:
        """Accept only known CAA/Internet Archive hosts and upgrade HTTP examples to HTTPS."""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or not parsed.hostname:
            return None
        host = parsed.hostname.casefold()
        if not any(host == suffix or host.endswith("." + suffix) for suffix in _ALLOWED_CAA_IMAGE_HOST_SUFFIXES):
            return None
        # The CAA documentation still contains historical HTTP redirect examples.
        # MusicArk never follows them in clear text; use the same trusted host/path
        # over HTTPS instead.
        return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment))

    def cached(self, artwork_key: str) -> ExternalArtworkCandidate | None:
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                "SELECT source, cache_path, mime, byte_size FROM external_artwork_cache WHERE artwork_key=?",
                (artwork_key,),
            ).fetchone()
        if row is None or not Path(str(row[1])).is_file():
            return None
        return ExternalArtworkCandidate(source=str(row[0]), cache_path=str(row[1]), mime=row[2])

    def fetch(self, artwork_key: str, source: str, url: str) -> ExternalArtworkCandidate | None:
        existing = self.cached(artwork_key)
        if existing is not None:
            return existing
        current = self._normalize_trusted_url(url)
        if current is None:
            return None
        response = self._transport.get(current, headers={"Accept": "image/*"})
        # The generic transport never follows redirects. Follow a bounded
        # CAA/Internet Archive redirect chain only after validating every hop.
        for _ in range(3):
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            location = self._normalize_trusted_url(response.headers.get("location", ""))
            if location is None:
                return None
            current = location
            response = self._transport.get(current, headers={"Accept": "image/*"})
        if response.status_code != 200:
            return None
        mime = (response.headers.get("content-type") or "").split(";", 1)[0].strip().casefold()
        if mime not in {"image/jpeg", "image/jpg", "image/png"}:
            return None
        data = response.content
        if not data or len(data) > _MAX_ARTWORK_BYTES:
            return None
        suffix = ".png" if mime == "image/png" else ".jpg"
        safe = hashlib.sha256(artwork_key.encode("utf-8")).hexdigest()
        directory = self._root / source
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{safe}{suffix}"
        path.write_bytes(data)
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO external_artwork_cache(artwork_key, source, cache_path, mime, byte_size, updated_at)
                    VALUES(?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(artwork_key) DO UPDATE SET
                        source=excluded.source,
                        cache_path=excluded.cache_path,
                        mime=excluded.mime,
                        byte_size=excluded.byte_size,
                        updated_at=excluded.updated_at
                    """,
                    (artwork_key, source, str(path.resolve()), mime, len(data)),
                )
        return ExternalArtworkCandidate(source=source, cache_path=str(path.resolve()), source_url=current, mime=mime)
