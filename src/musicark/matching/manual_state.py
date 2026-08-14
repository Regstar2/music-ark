"""Preserve manual links while marking materially changed inputs as stale."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from .fingerprints import local_file_fingerprint, provider_fingerprint

_STALE_PREFIX = "manual_match_stale"


class ManualMatchState:
    """Track the metadata reference used when a manual link was confirmed.

    Automatic matching must never silently overwrite a manual decision. If provider
    metadata or the linked local file changes, the link stays intact but the result is
    marked stale through its reason until the user explicitly confirms it again.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def store_reference(self, provider_id: str, external_id: str) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT mr.local_file_id, pt.payload_json
                    FROM matching_results mr
                    JOIN provider_tracks pt
                      ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                    WHERE mr.provider_id=? AND mr.external_id=? AND mr.manual=1
                    """,
                    (provider_id, external_id),
                ).fetchone()
                if row is None or row[0] is None:
                    return
                try:
                    payload = json.loads(row[1] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                provider_fp = provider_fingerprint(provider_id, external_id, payload)
                local_fp = self._local_fingerprint_conn(conn, int(row[0]))
                if local_fp is None:
                    return
                with conn:
                    conn.execute(
                        """
                        UPDATE matching_results
                        SET provider_fingerprint=?, local_fingerprint=?,
                            reason='manual_accept', updated_at=datetime('now')
                        WHERE provider_id=? AND external_id=? AND manual=1
                        """,
                        (provider_fp, local_fp, provider_id, external_id),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to store manual matching fingerprints.") from exc

    def mark_if_stale(
        self,
        provider_id: str,
        external_id: str,
        existing: dict[str, Any],
        current_provider_fingerprint: str,
    ) -> bool:
        if str(existing.get("reason") or "").startswith(_STALE_PREFIX):
            return True
        local_file_id = existing.get("local_file_id")
        if local_file_id is None:
            return False
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                current_local = self._local_fingerprint_conn(conn, int(local_file_id))
                if current_local is None:
                    return False
                previous_provider = str(existing.get("provider_fingerprint") or "")
                previous_local = str(existing.get("local_fingerprint") or "")

                # Compatibility with manual links created before reference tracking:
                # establish a baseline once instead of immediately calling them stale.
                if not previous_provider or not previous_local:
                    with conn:
                        conn.execute(
                            """
                            UPDATE matching_results
                            SET provider_fingerprint=?, local_fingerprint=?, updated_at=datetime('now')
                            WHERE provider_id=? AND external_id=? AND manual=1
                            """,
                            (
                                current_provider_fingerprint,
                                current_local,
                                provider_id,
                                external_id,
                            ),
                        )
                    return False

                changed: list[str] = []
                if previous_provider != current_provider_fingerprint:
                    changed.append("provider_metadata")
                if previous_local != current_local:
                    changed.append("local_metadata")
                if not changed:
                    return False

                reason = f"{_STALE_PREFIX}:{'+'.join(changed)}"
                with conn:
                    conn.execute(
                        """
                        UPDATE matching_results
                        SET reason=?, updated_at=datetime('now')
                        WHERE provider_id=? AND external_id=? AND manual=1
                        """,
                        (reason, provider_id, external_id),
                    )
                return True
        except sqlite3.Error as exc:
            raise StorageError("Failed to evaluate manual matching staleness.") from exc

    @staticmethod
    def is_stale_reason(reason: str | None) -> bool:
        return str(reason or "").startswith(_STALE_PREFIX)

    @staticmethod
    def _local_fingerprint_conn(conn: sqlite3.Connection, local_file_id: int) -> str | None:
        row = conn.execute(
            """
            SELECT path, file_size, modified_ns, title, artists_json, album,
                   duration_seconds, codec
            FROM local_audio_files WHERE id=?
            """,
            (local_file_id,),
        ).fetchone()
        return local_file_fingerprint(row) if row is not None else None
