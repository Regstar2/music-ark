"""Current Yandex matching scope and active Local Library policy."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError


_SCOPE_KEY = "matching_current_collection"
_PLAYLIST_PREFIX = "playlist:"


def _provider_identity_sql(item_alias: str = "pci") -> str:
    return f"""
        CASE
            WHEN json_valid({item_alias}.payload_json)
            THEN COALESCE(
                NULLIF(CAST(json_extract({item_alias}.payload_json, '$.external_id') AS TEXT), ''),
                {item_alias}.external_id
            )
            ELSE {item_alias}.external_id
        END
    """


class MatchingScopeState:
    """Persist current Yandex collection and enforce Local Library ownership.

    Compatibility: databases with no configured Local Library roots retain the
    historical v0.5 behaviour. Once at least one enabled root exists, only files
    owned by enabled roots are valid matching candidates.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)

    def active_collections(self, provider_id: str = "yandex_music") -> set[str]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT collection_id
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND active=1
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read active matching collections.") from exc
        return {str(row[0]) for row in rows if str(row[0] or "").strip()}

    def current_collection(self, provider_id: str = "yandex_music") -> str:
        active = self.active_collections(provider_id)
        if not active:
            return ""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT value FROM app_metadata WHERE key=?",
                    (_SCOPE_KEY,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read current matching collection.") from exc
        stored = str(row[0] or "").strip() if row else ""
        if stored in active:
            return stored
        if "liked" in active:
            return "liked"
        return ""

    def resolve_collection(
        self,
        collection_id: str | None,
        provider_id: str = "yandex_music",
    ) -> str:
        if collection_id is None:
            return self.current_collection(provider_id)
        clean = str(collection_id).strip()
        if not clean:
            return ""
        active = self.active_collections(provider_id)
        if active and clean not in active:
            raise ValueError(f"Yandex collection '{clean}' is not active in the local cache.")
        return clean

    def set_collection(
        self,
        collection_id: str,
        *,
        provider_id: str = "yandex_music",
    ) -> str:
        clean = str(collection_id).strip()
        active = self.active_collections(provider_id)
        if clean and active and clean not in active:
            raise ValueError(f"Yandex collection '{clean}' is not active in the local cache.")
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO app_metadata(key, value)
                        VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value
                        """,
                        (_SCOPE_KEY, clean),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist current matching collection.") from exc
        return clean

    def set_liked(self, provider_id: str = "yandex_music") -> str:
        active = self.active_collections(provider_id)
        if "liked" not in active:
            return self.current_collection(provider_id)
        return self.set_collection("liked", provider_id=provider_id)

    def set_playlist(
        self,
        external_id: str,
        *,
        provider_id: str = "yandex_music",
    ) -> str:
        clean = str(external_id).strip()
        if not clean:
            raise ValueError("Playlist external id is required.")
        return self.set_collection(
            f"{_PLAYLIST_PREFIX}{clean}",
            provider_id=provider_id,
        )

    def ensure_default(self, provider_id: str = "yandex_music") -> str:
        current = self.current_collection(provider_id)
        if current:
            return current
        return self.set_liked(provider_id)

    def clear(self) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute("DELETE FROM app_metadata WHERE key=?", (_SCOPE_KEY,))
        except sqlite3.Error as exc:
            raise StorageError("Failed to clear current matching collection.") from exc

    def external_ids(
        self,
        *,
        provider_id: str,
        collection_id: str,
    ) -> set[str] | None:
        """Return active provider identities; None means legacy provider_tracks mode."""
        active = self.active_collections(provider_id)
        if not active:
            return None
        params: list[Any] = [provider_id]
        collection_filter = ""
        if collection_id:
            collection_filter = "AND pci.collection_id=?"
            params.append(collection_id)
        identity_sql = _provider_identity_sql()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    f"""
                    SELECT DISTINCT {identity_sql} AS external_id
                    FROM provider_collection_items pci
                    JOIN provider_collection_snapshots pcs
                      ON pcs.provider_id=pci.provider_id
                     AND pcs.collection_id=pci.collection_id
                    WHERE pci.provider_id=?
                      AND pcs.active=1
                      {collection_filter}
                    """,
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read matching scope identities.") from exc
        return {
            str(row[0])
            for row in rows
            if row[0] is not None and str(row[0]).strip()
        }

    def active_local_count(self) -> int:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                roots = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM local_library_roots WHERE enabled=1"
                    ).fetchone()[0]
                )
                if roots:
                    row = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM local_audio_files laf
                        JOIN local_library_roots llr
                          ON llr.id=laf.library_root_id AND llr.enabled=1
                        WHERE laf.availability='available'
                        """
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM local_audio_files WHERE availability='available'"
                    ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to count active Local Library tracks.") from exc
        return int((row or (0,))[0] or 0)

    def summary(
        self,
        repository: Any,
        *,
        provider_id: str,
        collection_id: str,
    ) -> dict[str, Any]:
        scoped_ids = self.external_ids(
            provider_id=provider_id,
            collection_id=collection_id,
        )
        if scoped_ids is None:
            return repository.summary(provider_id)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT external_id, status
                    FROM matching_results
                    WHERE provider_id=?
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to compute scoped matching summary.") from exc
        counts = {"matched": 0, "conflict": 0, "unmatched": 0}
        for external_id, status in rows:
            if str(external_id) not in scoped_ids:
                continue
            key = str(status)
            if key in counts:
                counts[key] += 1
        return {
            "providerId": provider_id,
            "collectionId": collection_id,
            "yandexTracks": len(scoped_ids),
            "localTracks": self.active_local_count(),
            "processed": sum(counts.values()),
            "matched": counts["matched"],
            "conflicts": counts["conflict"],
            "unmatched": counts["unmatched"],
        }

    def invalidate_non_library_matches(self) -> int:
        """Invalidate local matches/candidates outside the configured Local Library."""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                roots = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM local_library_roots WHERE enabled=1"
                    ).fetchone()[0]
                )
                if roots:
                    valid = """
                        SELECT laf.id
                        FROM local_audio_files laf
                        JOIN local_library_roots llr
                          ON llr.id=laf.library_root_id AND llr.enabled=1
                        WHERE laf.availability='available'
                    """
                    reason = "local_file_outside_library"
                else:
                    valid = """
                        SELECT id FROM local_audio_files
                        WHERE availability='available'
                    """
                    reason = "local_file_missing"
                with conn:
                    stale = conn.execute(
                        f"""
                        SELECT provider_id, external_id
                        FROM matching_results
                        WHERE local_file_id IS NOT NULL
                          AND local_file_id NOT IN ({valid})
                        """
                    ).fetchall()
                    conn.execute(
                        f"""
                        DELETE FROM track_links
                        WHERE local_file_id IS NOT NULL
                          AND local_file_id NOT IN ({valid})
                        """
                    )
                    conn.execute(
                        f"""
                        DELETE FROM match_conflicts
                        WHERE status='open'
                          AND local_file_id NOT IN ({valid})
                        """
                    )
                    conn.execute(
                        f"""
                        UPDATE matching_results
                        SET status='unmatched', local_file_id=NULL, confidence=0,
                            method='automatic', score_breakdown_json='{{}}', reason=?,
                            manual=0, updated_at=datetime('now')
                        WHERE local_file_id IS NOT NULL
                          AND local_file_id NOT IN ({valid})
                        """,
                        (reason,),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to invalidate out-of-library matching state.") from exc
        return len(stale)

    def assert_local_file_allowed(self, local_file_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                roots = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM local_library_roots WHERE enabled=1"
                    ).fetchone()[0]
                )
                if roots:
                    row = conn.execute(
                        """
                        SELECT 1
                        FROM local_audio_files laf
                        JOIN local_library_roots llr
                          ON llr.id=laf.library_root_id AND llr.enabled=1
                        WHERE laf.id=? AND laf.availability='available'
                        """,
                        (int(local_file_id),),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT 1 FROM local_audio_files
                        WHERE id=? AND availability='available'
                        """,
                        (int(local_file_id),),
                    ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to validate Local Library candidate.") from exc
        if row is None:
            raise ValueError("Selected local candidate is outside the active Local Library.")

    def clean_search(self, search: str) -> str:
        """A pasted configured root is Local scope, not a result-search filter."""
        clean = str(search or "").strip()
        if len(clean) >= 2 and clean[0] == clean[-1] and clean[0] in {"'", '"'}:
            clean = clean[1:-1].strip()
        if not clean:
            return ""

        def key(value: str) -> str:
            return value.replace("\\", "/").rstrip("/").casefold()

        candidate = key(clean)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT path FROM local_library_roots WHERE enabled=1"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to inspect Local Library roots.") from exc
        if any(key(str(row[0] or "")) == candidate for row in rows):
            return ""
        return clean
