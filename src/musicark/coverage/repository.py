"""SQL-backed derived Library Coverage queries for MusicArk v0.6."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from musicark.matching.fingerprints import local_file_fingerprint, provider_fingerprint
from musicark.matching.policy import MATCHER_VERSION
from musicark.storage.matching_storage import MatchingStorageRepository

from .actions import CoverageActionStore
from .sql import coverage_base_cte


_ALLOWED_STATUSES = {"covered", "missing", "needs_review", "not_analyzed"}
_ALLOWED_ACTIONS = {"wanted", "ignored", "unreviewed"}
_ALLOWED_VARIANTS = {"same", "altered", "different_version", "uncertain", "not_checked"}


class CoverageRepository:
    """Read coverage from authoritative provider/matching/variant/local tables.

    Coverage itself is never persisted. Only the user's wanted/ignored decision is.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._matching = MatchingStorageRepository(database_path)
        self._actions = CoverageActionStore(database_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.create_function(
            "musicark_provider_fingerprint",
            3,
            self._provider_fingerprint_sql,
            deterministic=True,
        )
        conn.create_function(
            "musicark_local_fingerprint",
            8,
            self._local_fingerprint_sql,
            deterministic=True,
        )
        return conn

    @staticmethod
    def _provider_fingerprint_sql(
        provider_id: object,
        external_id: object,
        payload_json: object,
    ) -> str:
        try:
            payload = json.loads(str(payload_json or "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return provider_fingerprint(str(provider_id or ""), str(external_id or ""), payload)

    @staticmethod
    def _local_fingerprint_sql(*values: object) -> str:
        if not values or values[0] is None:
            return ""
        try:
            return local_file_fingerprint(tuple(values))
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _base_cte() -> str:
        return coverage_base_cte()

    def _context_params(self, provider_id: str, collection_id: str) -> list[Any]:
        return [
            provider_id,
            collection_id,
            MATCHER_VERSION,
            self._matching.local_library_fingerprint(),
        ]

    def summary(
        self,
        *,
        provider_id: str,
        collection_id: str = "",
    ) -> dict[str, Any]:
        sql = self._base_cte() + """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN coverage_status='covered' THEN 1 ELSE 0 END) AS covered,
            SUM(CASE WHEN coverage_status='missing' THEN 1 ELSE 0 END) AS missing,
            SUM(CASE WHEN coverage_status='needs_review' THEN 1 ELSE 0 END) AS needs_review,
            SUM(CASE WHEN coverage_status='not_analyzed' THEN 1 ELSE 0 END) AS not_analyzed,
            SUM(CASE WHEN coverage_status='covered' AND variant_status='same' THEN 1 ELSE 0 END) AS variant_same,
            SUM(CASE WHEN coverage_status='covered' AND variant_status='altered' THEN 1 ELSE 0 END) AS variant_altered,
            SUM(CASE WHEN coverage_status='covered' AND variant_status='different_version' THEN 1 ELSE 0 END) AS variant_different,
            SUM(CASE WHEN coverage_status='covered' AND variant_status='uncertain' THEN 1 ELSE 0 END) AS variant_uncertain,
            SUM(CASE WHEN coverage_status='covered' AND variant_status='not_checked' THEN 1 ELSE 0 END) AS variant_not_checked,
            SUM(CASE WHEN coverage_status='missing' AND user_action='wanted' THEN 1 ELSE 0 END) AS wanted_missing,
            SUM(CASE WHEN coverage_status='missing' AND user_action='ignored' THEN 1 ELSE 0 END) AS ignored_missing,
            SUM(CASE WHEN coverage_status='missing' AND user_action='unreviewed' THEN 1 ELSE 0 END) AS unreviewed_missing
        FROM coverage_base
        """
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    sql, self._context_params(provider_id, collection_id)
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to compute Library Coverage summary.") from exc

        values = [int(value or 0) for value in (row or (0,) * 13)]
        (
            total,
            covered,
            missing,
            needs_review,
            not_analyzed,
            same,
            altered,
            different,
            uncertain,
            not_checked,
            wanted,
            ignored,
            unreviewed,
        ) = values
        analyzed = total - not_analyzed
        return {
            "providerId": provider_id,
            "collectionId": collection_id,
            "total": total,
            "covered": covered,
            "missing": missing,
            "needsReview": needs_review,
            "notAnalyzed": not_analyzed,
            "coveragePercent": round((covered / total * 100.0) if total else 0.0, 1),
            "matchingAnalyzedPercent": round(
                (analyzed / total * 100.0) if total else 0.0, 1
            ),
            "variantVerification": {
                "same": same,
                "altered": altered,
                "differentVersion": different,
                "uncertain": uncertain,
                "notChecked": not_checked,
            },
            "missingActions": {
                "wanted": wanted,
                "ignored": ignored,
                "unreviewed": unreviewed,
            },
        }

    def list_tracks(
        self,
        *,
        provider_id: str,
        collection_id: str = "",
        status: str = "",
        search: str = "",
        sort: str = "artist",
        user_action: str = "",
        variant_status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        page_limit = max(1, min(int(limit), 2000))
        page_offset = max(0, int(offset))
        where: list[str] = ["1=1"]
        params = self._context_params(provider_id, collection_id)

        clean_status = status.strip().casefold()
        if clean_status in _ALLOWED_STATUSES:
            where.append("coverage_status=?")
            params.append(clean_status)

        clean_action = user_action.strip().casefold()
        if clean_action in _ALLOWED_ACTIONS:
            where.append("user_action=?")
            params.append(clean_action)

        clean_variant = variant_status.strip().casefold()
        if clean_variant in _ALLOWED_VARIANTS:
            where.append("coverage_status='covered' AND variant_status=?")
            params.append(clean_variant)

        query = search.strip()
        if query:
            needle = f"%{query}%"
            where.append(
                "("
                "COALESCE(json_extract(payload_json,'$.title'),'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(json_extract(payload_json,'$.artists'),'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(json_extract(payload_json,'$.album_title'),"
                "            json_extract(payload_json,'$.album'),'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(collection_search,'') LIKE ? COLLATE NOCASE"
                ")"
            )
            params.extend([needle, needle, needle, needle])

        order_by = {
            "artist": (
                "COALESCE(json_extract(payload_json,'$.artists[0]'),'') COLLATE NOCASE, "
                "COALESCE(json_extract(payload_json,'$.title'),'') COLLATE NOCASE, external_id"
            ),
            "title": (
                "COALESCE(json_extract(payload_json,'$.title'),'') COLLATE NOCASE, "
                "COALESCE(json_extract(payload_json,'$.artists[0]'),'') COLLATE NOCASE, external_id"
            ),
            "album": (
                "COALESCE(json_extract(payload_json,'$.album_title'),"
                "         json_extract(payload_json,'$.album'),'') COLLATE NOCASE, "
                "COALESCE(json_extract(payload_json,'$.artists[0]'),'') COLLATE NOCASE, external_id"
            ),
            "collection": "COALESCE(collection_search,'') COLLATE NOCASE, external_id",
            "status": "coverage_status, external_id",
            "position": "COALESCE(scope_position, 2147483647), external_id",
        }.get(sort, "COALESCE(json_extract(payload_json,'$.artists[0]'),'') COLLATE NOCASE, external_id")

        where_sql = " AND ".join(where)
        base = self._base_cte()
        try:
            with closing(self._connect()) as conn:
                total = int(
                    conn.execute(
                        base + f"SELECT COUNT(*) FROM coverage_base WHERE {where_sql}",
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    base
                    + f"""
                    SELECT provider_id, external_id, payload_json, collections_json,
                           scope_position, coverage_status, matching_status,
                           local_file_id, confidence, method, reason, manual,
                           matching_updated_at, local_path, local_title,
                           local_artists_json, local_album, local_duration_seconds,
                           variant_status, user_action
                    FROM coverage_base
                    WHERE {where_sql}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_limit, page_offset],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list Library Coverage tracks.") from exc

        return [self._row(row) for row in rows], total

    def get_track(
        self,
        *,
        provider_id: str,
        external_id: str,
    ) -> dict[str, Any] | None:
        sql = self._base_cte() + """
        SELECT provider_id, external_id, payload_json, collections_json,
               scope_position, coverage_status, matching_status,
               local_file_id, confidence, method, reason, manual,
               matching_updated_at, local_path, local_title,
               local_artists_json, local_album, local_duration_seconds,
               variant_status, user_action
        FROM coverage_base
        WHERE external_id=?
        LIMIT 1
        """
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    sql,
                    [*self._context_params(provider_id, ""), external_id],
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load Library Coverage track.") from exc
        return self._row(row) if row else None

    def collections(self, *, provider_id: str) -> list[dict[str, Any]]:
        # This is intentionally metadata-only. Coverage counts are produced by summary
        # for the selected scope, avoiding an expensive all-playlists analytics query.
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    """
                    SELECT collection_id, collection_type, external_id,
                           CASE WHEN collection_id='liked' THEN 'Мне нравится'
                                ELSE COALESCE(NULLIF(title,''), collection_id) END,
                           item_count, source_position
                    FROM provider_collection_snapshots
                    WHERE provider_id=? AND active=1
                    ORDER BY CASE WHEN collection_id='liked' THEN 0 ELSE 1 END,
                             source_position, title COLLATE NOCASE
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list Library Coverage collections.") from exc

        return [
            {
                "id": str(row[0]),
                "type": str(row[1] or ("liked" if row[0] == "liked" else "playlist")),
                "externalId": row[2],
                "title": str(row[3] or row[0]),
                "itemCount": int(row[4] or 0),
                "position": int(row[5] or 0),
            }
            for row in rows
        ]

    def set_action(self, *, provider_id: str, external_id: str, action: str) -> str:
        return self._actions.set_action(
            provider_id=provider_id, external_id=external_id, action=action
        )

    def set_actions(
        self, *, provider_id: str, external_ids: list[str], action: str
    ) -> dict[str, Any]:
        return self._actions.set_actions(
            provider_id=provider_id, external_ids=external_ids, action=action
        )

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            provider = json.loads(row[2] or "{}")
        except (TypeError, json.JSONDecodeError):
            provider = {}
        if not isinstance(provider, dict):
            provider = {}

        try:
            collections = json.loads(row[3] or "[]")
        except (TypeError, json.JSONDecodeError):
            collections = []
        if not isinstance(collections, list):
            collections = []

        try:
            local_artists = json.loads(row[15] or "[]")
        except (TypeError, json.JSONDecodeError):
            local_artists = []
        if not isinstance(local_artists, list):
            local_artists = []

        coverage_status = str(row[5])
        local = None
        if row[7] is not None:
            local = {
                "id": int(row[7]),
                "path": row[13],
                "title": row[14],
                "artists": local_artists,
                "album": row[16],
                "durationSeconds": row[17],
            }

        return {
            "providerId": str(row[0]),
            "externalId": str(row[1]),
            "provider": provider,
            "collections": collections,
            "scopePosition": row[4],
            "coverageStatus": coverage_status,
            "matchingStatus": row[6],
            "localFileId": row[7],
            "confidence": float(row[8] or 0),
            "method": row[9],
            "reason": row[10] or "",
            "manual": bool(row[11]),
            "matchingUpdatedAt": row[12],
            "local": local,
            "variantStatus": (
                str(row[18] or "not_checked")
                if coverage_status == "covered"
                else None
            ),
            "userAction": str(row[19] or "unreviewed"),
        }
