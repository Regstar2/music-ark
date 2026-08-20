"""Bounded SQLite cache for external metadata responses."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


class ExternalMetadataCache:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def get(self, key: str) -> tuple[bool, Any] | None:
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                "SELECT payload_json, negative, expires_at FROM external_metadata_cache WHERE cache_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        try:
            expires = datetime.fromisoformat(str(row[2]).replace("Z", "+00:00"))
        except ValueError:
            return None
        if expires <= self._now():
            return None
        try:
            payload = json.loads(str(row[0]))
        except json.JSONDecodeError:
            return None
        return bool(row[1]), payload

    def put(self, key: str, provider: str, payload: Any, *, negative: bool = False, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else (300 if negative else 86400)
        expires = self._now() + timedelta(seconds=max(30, ttl))
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO external_metadata_cache(cache_key, provider_id, payload_json, negative, expires_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(cache_key) DO UPDATE SET
                        provider_id=excluded.provider_id,
                        payload_json=excluded.payload_json,
                        negative=excluded.negative,
                        expires_at=excluded.expires_at,
                        updated_at=excluded.updated_at
                    """,
                    (key, provider, json.dumps(payload, ensure_ascii=False), 1 if negative else 0, expires.isoformat()),
                )
