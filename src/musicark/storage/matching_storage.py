"""SQLite persistence and indexed lookup for MusicArk matching."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.matching.models import MatchConflict, MatchDecision, MatchMethod, MatchStatus, Track, TrackLink
from musicark.matching.normalize import artists_key, normalize_artists, normalize_text
from musicark.matching.policy import MATCHER_VERSION, PERSISTED_CONFLICT_CANDIDATES


class MatchingStorageRepository:
    """Read provider/local candidates and persist matching decisions transactionally."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    # ---- Provider/local inputs -------------------------------------------------
    def list_provider_track_candidates(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        where = "WHERE pt.provider_id=?" if provider_id else ""
        params: tuple[Any, ...] = (provider_id,) if provider_id else ()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    f"""
                    SELECT pt.provider_id, pt.external_id, pt.payload_json, ts.id
                    FROM provider_tracks pt
                    LEFT JOIN track_sources ts
                      ON ts.provider_id = pt.provider_id AND ts.external_id = pt.external_id
                    {where}
                    ORDER BY pt.id
                    """,
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read provider track candidates.") from exc
        result: list[dict[str, Any]] = []
        for provider, external_id, payload_json, source_row_id in rows:
            try:
                payload = json.loads(payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            result.append(
                {
                    "provider_id": str(provider),
                    "external_id": str(external_id),
                    "payload": payload if isinstance(payload, dict) else {},
                    "source_row_id": source_row_id,
                }
            )
        return result

    def find_local_candidates(
        self,
        *,
        normalized_title: str,
        normalized_artists: str,
        duration_seconds: float | None,
        limit: int,
        excluded_local_ids: set[int],
    ) -> list[dict[str, Any]]:
        """Return a bounded candidate set using indexed equality/range lookups.

        This deliberately issues a few small SQL lookups instead of loading the local
        library and computing a Cartesian product in Python.
        """
        if not normalized_title and not normalized_artists:
            return []
        page_limit = max(1, min(int(limit), 100))
        found: dict[int, tuple[Any, ...]] = {}

        def add_rows(conn: sqlite3.Connection, sql: str, params: list[Any]) -> None:
            remaining = page_limit - len(found)
            if remaining <= 0:
                return
            for row in conn.execute(sql, [*params, remaining]).fetchall():
                file_id = int(row[0])
                if file_id not in excluded_local_ids:
                    found.setdefault(file_id, row)
                    if len(found) >= page_limit:
                        break

        columns = """
            id, path, title, artists_json, album, duration_seconds, codec,
            metadata_json, normalized_title, normalized_artists_text,
            duration_bucket, modified_ns, updated_at
        """
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                if normalized_title:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_title=?
                        ORDER BY CASE WHEN normalized_artists_text=? THEN 0 ELSE 1 END,
                                 COALESCE(duration_seconds, 0)
                        LIMIT ?
                        """,
                        [normalized_title, normalized_artists],
                    )
                if normalized_title and len(found) < page_limit:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_title LIKE ?
                        ORDER BY CASE WHEN normalized_artists_text=? THEN 0 ELSE 1 END,
                                 LENGTH(normalized_title)
                        LIMIT ?
                        """,
                        [f"{normalized_title} %", normalized_artists],
                    )
                if normalized_artists and duration_seconds is not None and len(found) < page_limit:
                    bucket = int(round(float(duration_seconds))) // 5
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available'
                          AND normalized_artists_text=?
                          AND duration_bucket BETWEEN ? AND ?
                        ORDER BY ABS(COALESCE(duration_seconds, 0) - ?)
                        LIMIT ?
                        """,
                        [normalized_artists, bucket - 2, bucket + 2, float(duration_seconds)],
                    )
                if normalized_artists and len(found) < page_limit:
                    add_rows(
                        conn,
                        f"""
                        SELECT {columns} FROM local_audio_files
                        WHERE availability='available' AND normalized_artists_text=?
                        ORDER BY CASE WHEN normalized_title=? THEN 0 ELSE 1 END, normalized_title
                        LIMIT ?
                        """,
                        [normalized_artists, normalized_title],
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to generate local matching candidates.") from exc
        return [self._local_row(row) for row in found.values()]

    @staticmethod
    def _local_row(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            artists = json.loads(row[3] or "[]")
        except json.JSONDecodeError:
            artists = []
        try:
            metadata = json.loads(row[7] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": int(row[0]),
            "path": row[1],
            "title": row[2],
            "artists": artists if isinstance(artists, list) else [],
            "album": row[4],
            "duration_seconds": row[5],
            "codec": row[6],
            "metadata_json": metadata if isinstance(metadata, dict) else {},
            "tag_title_present": bool(isinstance(metadata, dict) and metadata.get("title")),
            "normalized_title": row[8] or "",
            "normalized_artists": row[9] or "",
            "duration_bucket": row[10],
            "modified_ns": row[11],
            "updated_at": row[12],
        }

    def local_library_fingerprint(self) -> str:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(MAX(updated_at), '')
                    FROM local_audio_files WHERE availability='available'
                    """
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to fingerprint Local Library.") from exc
        payload = f"{row[0]}|{row[1]}|{row[2]}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def cleanup_stale_links(self) -> int:
        """Invalidate results whose local file disappeared since the previous run."""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    stale = conn.execute(
                        """
                        SELECT provider_id, external_id FROM matching_results
                        WHERE local_file_id IS NOT NULL
                          AND local_file_id NOT IN (SELECT id FROM local_audio_files)
                        """
                    ).fetchall()
                    conn.execute(
                        "DELETE FROM track_links WHERE local_file_id NOT IN (SELECT id FROM local_audio_files)"
                    )
                    conn.execute(
                        """
                        UPDATE matching_results
                        SET status='unmatched', local_file_id=NULL, confidence=0,
                            method='automatic', score_breakdown_json='{}',
                            reason='local_file_missing', manual=0, updated_at=datetime('now')
                        WHERE local_file_id IS NOT NULL
                          AND local_file_id NOT IN (SELECT id FROM local_audio_files)
                        """
                    )
                    return len(stale)
        except sqlite3.Error as exc:
            raise StorageError("Failed to invalidate stale matching links.") from exc

    # ---- Results ---------------------------------------------------------------
    def get_existing_result(self, provider_id: str, external_id: str) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT status, local_file_id, confidence, method, score_breakdown_json,
                           reason, matcher_version, provider_fingerprint, local_fingerprint,
                           manual, updated_at
                    FROM matching_results WHERE provider_id=? AND external_id=?
                    """,
                    (provider_id, external_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load matching result.") from exc
        if row is None:
            return None
        return {
            "status": row[0],
            "local_file_id": row[1],
            "confidence": float(row[2] or 0),
            "method": row[3],
            "breakdown": self._json_dict(row[4]),
            "reason": row[5],
            "matcher_version": int(row[6] or 0),
            "provider_fingerprint": row[7] or "",
            "local_fingerprint": row[8] or "",
            "manual": bool(row[9]),
            "updated_at": row[10],
        }

    def rejected_local_ids(self, provider_id: str, external_id: str) -> set[int]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT local_file_id FROM match_conflicts
                    WHERE source_provider_id=? AND source_external_id=? AND status='rejected'
                    """,
                    (provider_id, external_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load rejected matching candidates.") from exc
        return {int(row[0]) for row in rows}

    def persist_batch(self, decisions: Iterable[MatchDecision]) -> None:
        items = list(decisions)
        if not items:
            return
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    for decision in items:
                        self._persist_decision(conn, decision)
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist matching batch.") from exc

    def _persist_decision(self, conn: sqlite3.Connection, decision: MatchDecision) -> None:
        provider_id = decision.provider_id
        external_id = decision.external_id
        conn.execute(
            """
            DELETE FROM track_links
            WHERE source_provider_id=? AND source_external_id=? AND match_method<>'manual'
            """,
            (provider_id, external_id),
        )
        conn.execute(
            """
            DELETE FROM match_conflicts
            WHERE source_provider_id=? AND source_external_id=? AND status='open'
            """,
            (provider_id, external_id),
        )
        conn.execute(
            """
            INSERT INTO matching_results(
                provider_id, external_id, status, local_file_id, confidence, method,
                score_breakdown_json, reason, matcher_version, provider_fingerprint,
                local_fingerprint, manual
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(provider_id, external_id) DO UPDATE SET
                status=excluded.status,
                local_file_id=excluded.local_file_id,
                confidence=excluded.confidence,
                method=excluded.method,
                score_breakdown_json=excluded.score_breakdown_json,
                reason=excluded.reason,
                matcher_version=excluded.matcher_version,
                provider_fingerprint=excluded.provider_fingerprint,
                local_fingerprint=excluded.local_fingerprint,
                manual=0,
                updated_at=datetime('now')
            """,
            (
                provider_id,
                external_id,
                decision.status.value,
                decision.local_file_id,
                decision.confidence,
                decision.method.value,
                json.dumps(decision.breakdown, ensure_ascii=False, sort_keys=True),
                decision.reason,
                MATCHER_VERSION,
                decision.provider_fingerprint,
                decision.local_fingerprint,
            ),
        )

        if decision.status is MatchStatus.MATCHED and decision.local_file_id is not None:
            track = self._track_from_payload(decision.provider_payload)
            track_id = self._upsert_track_conn(conn, track)
            conn.execute(
                """
                INSERT INTO track_links(
                    track_id, source_provider_id, source_external_id, local_file_id,
                    confidence, match_method, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_provider_id, source_external_id, local_file_id)
                DO UPDATE SET track_id=excluded.track_id, confidence=excluded.confidence,
                              match_method=excluded.match_method,
                              metadata_json=excluded.metadata_json,
                              updated_at=datetime('now')
                """,
                (
                    track_id,
                    provider_id,
                    external_id,
                    decision.local_file_id,
                    decision.confidence,
                    decision.method.value,
                    json.dumps(
                        {
                            "score": decision.breakdown,
                            "matcher_version": MATCHER_VERSION,
                            "automatic": True,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
        elif decision.status is MatchStatus.CONFLICT:
            rejected = self._rejected_ids_conn(conn, provider_id, external_id)
            for rank, candidate in enumerate(
                decision.candidates[:PERSISTED_CONFLICT_CANDIDATES], start=1
            ):
                if candidate.local_file_id in rejected:
                    continue
                conn.execute(
                    """
                    INSERT INTO match_conflicts(
                        source_provider_id, source_external_id, local_file_id,
                        confidence, reason, status, score_breakdown_json,
                        candidate_rank, matcher_version, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, datetime('now'))
                    """,
                    (
                        provider_id,
                        external_id,
                        candidate.local_file_id,
                        candidate.confidence,
                        decision.reason,
                        json.dumps(candidate.breakdown, ensure_ascii=False, sort_keys=True),
                        rank,
                        MATCHER_VERSION,
                    ),
                )

    def summary(self, provider_id: str = "yandex_music") -> dict[str, Any]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                provider_tracks = int(
                    conn.execute("SELECT COUNT(*) FROM provider_tracks WHERE provider_id=?", (provider_id,)).fetchone()[0]
                )
                local_tracks = int(
                    conn.execute("SELECT COUNT(*) FROM local_audio_files WHERE availability='available'").fetchone()[0]
                )
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*) FROM matching_results
                    WHERE provider_id=? GROUP BY status
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to compute matching summary.") from exc
        counts = {str(status): int(count) for status, count in rows}
        return {
            "providerId": provider_id,
            "yandexTracks": provider_tracks,
            "localTracks": local_tracks,
            "processed": sum(counts.values()),
            "matched": counts.get("matched", 0),
            "conflicts": counts.get("conflict", 0),
            "unmatched": counts.get("unmatched", 0),
        }

    def list_results(
        self,
        *,
        provider_id: str = "yandex_music",
        limit: int = 100,
        offset: int = 0,
        status: str = "",
        search: str = "",
        sort: str = "confidence",
    ) -> tuple[list[dict[str, Any]], int]:
        page_limit = max(1, min(int(limit), 500))
        page_offset = max(0, int(offset))
        where = ["mr.provider_id=?"]
        params: list[Any] = [provider_id]
        if status in {"matched", "conflict", "unmatched"}:
            where.append("mr.status=?")
            params.append(status)
        query = search.strip()
        if query:
            needle = f"%{query}%"
            where.append(
                "(pt.payload_json LIKE ? COLLATE NOCASE OR COALESCE(laf.title,'') LIKE ? COLLATE NOCASE "
                "OR COALESCE(laf.artists_json,'') LIKE ? COLLATE NOCASE OR COALESCE(laf.path,'') LIKE ? COLLATE NOCASE)"
            )
            params.extend([needle, needle, needle, needle])
        order_by = {
            "confidence": "mr.confidence DESC, mr.external_id",
            "artist": "pt.payload_json COLLATE NOCASE, mr.external_id",
            "title": "pt.payload_json COLLATE NOCASE, mr.external_id",
            "status": "mr.status, mr.confidence DESC",
        }.get(sort, "mr.confidence DESC, mr.external_id")
        where_sql = " AND ".join(where)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = int(
                    conn.execute(
                        f"""
                        SELECT COUNT(*) FROM matching_results mr
                        JOIN provider_tracks pt ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                        LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                        WHERE {where_sql}
                        """,
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    f"""
                    SELECT mr.provider_id, mr.external_id, mr.status, mr.local_file_id,
                           mr.confidence, mr.method, mr.score_breakdown_json, mr.reason,
                           mr.manual, mr.updated_at, pt.payload_json,
                           laf.path, laf.title, laf.artists_json, laf.album, laf.duration_seconds
                    FROM matching_results mr
                    JOIN provider_tracks pt ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                    LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                    WHERE {where_sql}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_limit, page_offset],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list matching results.") from exc
        return [self._result_row(row) for row in rows], total

    def get_result_detail(self, provider_id: str, external_id: str) -> dict[str, Any] | None:
        items, _ = self._result_query_for_identity(provider_id, external_id)
        if not items:
            return None
        item = items[0]
        item["candidates"] = self.list_conflict_candidates(provider_id, external_id)
        return item

    def _result_query_for_identity(self, provider_id: str, external_id: str) -> tuple[list[dict[str, Any]], int]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT mr.provider_id, mr.external_id, mr.status, mr.local_file_id,
                           mr.confidence, mr.method, mr.score_breakdown_json, mr.reason,
                           mr.manual, mr.updated_at, pt.payload_json,
                           laf.path, laf.title, laf.artists_json, laf.album, laf.duration_seconds
                    FROM matching_results mr
                    JOIN provider_tracks pt ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                    LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                    WHERE mr.provider_id=? AND mr.external_id=?
                    """,
                    (provider_id, external_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load matching result detail.") from exc
        return ([self._result_row(row)] if row else []), (1 if row else 0)

    def list_conflict_candidates(self, provider_id: str, external_id: str) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT mc.id, mc.local_file_id, mc.confidence, mc.score_breakdown_json,
                           mc.reason, mc.status, mc.candidate_rank,
                           laf.path, laf.title, laf.artists_json, laf.album, laf.duration_seconds, laf.codec
                    FROM match_conflicts mc
                    JOIN local_audio_files laf ON laf.id=mc.local_file_id
                    WHERE mc.source_provider_id=? AND mc.source_external_id=?
                      AND mc.status IN ('open','accepted','rejected')
                    ORDER BY CASE mc.status WHEN 'open' THEN 0 WHEN 'accepted' THEN 1 ELSE 2 END,
                             mc.candidate_rank, mc.confidence DESC
                    """,
                    (provider_id, external_id),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list conflict candidates.") from exc
        result = []
        for row in rows:
            try:
                artists = json.loads(row[9] or "[]")
            except json.JSONDecodeError:
                artists = []
            result.append(
                {
                    "conflictId": int(row[0]),
                    "localFileId": int(row[1]),
                    "confidence": float(row[2]),
                    "score": self._json_dict(row[3]),
                    "reason": row[4],
                    "status": row[5],
                    "rank": int(row[6] or 0),
                    "local": {
                        "path": row[7],
                        "title": row[8],
                        "artists": artists if isinstance(artists, list) else [],
                        "album": row[10],
                        "durationSeconds": row[11],
                        "codec": row[12],
                    },
                }
            )
        return result

    @staticmethod
    def _result_row(row: tuple[Any, ...]) -> dict[str, Any]:
        try:
            provider = json.loads(row[10] or "{}")
        except json.JSONDecodeError:
            provider = {}
        try:
            local_artists = json.loads(row[13] or "[]")
        except json.JSONDecodeError:
            local_artists = []
        local = None
        if row[3] is not None:
            local = {
                "id": int(row[3]),
                "path": row[11],
                "title": row[12],
                "artists": local_artists if isinstance(local_artists, list) else [],
                "album": row[14],
                "durationSeconds": row[15],
            }
        return {
            "providerId": row[0],
            "externalId": row[1],
            "status": row[2],
            "localFileId": row[3],
            "confidence": float(row[4] or 0),
            "method": row[5],
            "score": MatchingStorageRepository._json_dict(row[6]),
            "reason": row[7],
            "manual": bool(row[8]),
            "updatedAt": row[9],
            "provider": provider if isinstance(provider, dict) else {},
            "local": local,
        }

    # ---- Manual decisions ------------------------------------------------------
    def accept_manual(self, provider_id: str, external_id: str, local_file_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    provider_row = conn.execute(
                        "SELECT payload_json FROM provider_tracks WHERE provider_id=? AND external_id=?",
                        (provider_id, external_id),
                    ).fetchone()
                    local_row = conn.execute("SELECT id FROM local_audio_files WHERE id=?", (int(local_file_id),)).fetchone()
                    if provider_row is None or local_row is None:
                        raise StorageError("Provider track or local candidate is missing.")
                    payload = json.loads(provider_row[0] or "{}")
                    candidate = conn.execute(
                        """
                        SELECT confidence, score_breakdown_json FROM match_conflicts
                        WHERE source_provider_id=? AND source_external_id=? AND local_file_id=?
                        ORDER BY id DESC LIMIT 1
                        """,
                        (provider_id, external_id, int(local_file_id)),
                    ).fetchone()
                    confidence = float(candidate[0]) if candidate else 1.0
                    breakdown = self._json_dict(candidate[1]) if candidate else {"final": confidence}
                    track_id = self._upsert_track_conn(conn, self._track_from_payload(payload))
                    conn.execute(
                        "DELETE FROM track_links WHERE source_provider_id=? AND source_external_id=?",
                        (provider_id, external_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id, local_file_id,
                            confidence, match_method, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, 'manual', ?)
                        """,
                        (
                            track_id,
                            provider_id,
                            external_id,
                            int(local_file_id),
                            confidence,
                            json.dumps({"score": breakdown, "matcher_version": MATCHER_VERSION}, ensure_ascii=False),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO matching_results(
                            provider_id, external_id, status, local_file_id, confidence, method,
                            score_breakdown_json, reason, matcher_version,
                            provider_fingerprint, local_fingerprint, manual
                        ) VALUES (?, ?, 'matched', ?, ?, 'manual', ?, 'manual_accept', ?, '', '', 1)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            status='matched', local_file_id=excluded.local_file_id,
                            confidence=excluded.confidence, method='manual',
                            score_breakdown_json=excluded.score_breakdown_json,
                            reason='manual_accept', manual=1, updated_at=datetime('now')
                        """,
                        (
                            provider_id,
                            external_id,
                            int(local_file_id),
                            confidence,
                            json.dumps(breakdown, ensure_ascii=False, sort_keys=True),
                            MATCHER_VERSION,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE match_conflicts SET status=CASE WHEN local_file_id=? THEN 'accepted' ELSE 'superseded' END,
                               updated_at=datetime('now')
                        WHERE source_provider_id=? AND source_external_id=? AND status='open'
                        """,
                        (int(local_file_id), provider_id, external_id),
                    )
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            if isinstance(exc, StorageError):
                raise
            raise StorageError("Failed to persist manual matching acceptance.") from exc

    def reject_candidate(self, provider_id: str, external_id: str, local_file_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE match_conflicts SET status='rejected', updated_at=datetime('now')
                        WHERE source_provider_id=? AND source_external_id=? AND local_file_id=?
                          AND status='open'
                        """,
                        (provider_id, external_id, int(local_file_id)),
                    )
                    if cursor.rowcount == 0:
                        conn.execute(
                            """
                            INSERT INTO match_conflicts(
                                source_provider_id, source_external_id, local_file_id,
                                confidence, reason, status, score_breakdown_json,
                                candidate_rank, matcher_version, updated_at
                            ) VALUES (?, ?, ?, 0, 'manual_reject', 'rejected', '{}', 0, ?, datetime('now'))
                            """,
                            (provider_id, external_id, int(local_file_id), MATCHER_VERSION),
                        )
                    next_row = conn.execute(
                        """
                        SELECT local_file_id, confidence, score_breakdown_json
                        FROM match_conflicts
                        WHERE source_provider_id=? AND source_external_id=? AND status='open'
                        ORDER BY candidate_rank, confidence DESC LIMIT 1
                        """,
                        (provider_id, external_id),
                    ).fetchone()
                    if next_row:
                        conn.execute(
                            """
                            UPDATE matching_results
                            SET status='conflict', local_file_id=?, confidence=?,
                                score_breakdown_json=?, reason='manual_reject_remaining_candidates',
                                manual=0, updated_at=datetime('now')
                            WHERE provider_id=? AND external_id=?
                            """,
                            (next_row[0], next_row[1], next_row[2], provider_id, external_id),
                        )
                    else:
                        conn.execute(
                            """
                            UPDATE matching_results
                            SET status='unmatched', local_file_id=NULL, confidence=0,
                                score_breakdown_json='{}', reason='manual_reject_no_candidates',
                                manual=0, updated_at=datetime('now')
                            WHERE provider_id=? AND external_id=?
                            """,
                            (provider_id, external_id),
                        )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist matching rejection.") from exc

    def accept_conflict_by_id(self, conflict_id: int) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT source_provider_id, source_external_id, local_file_id
                    FROM match_conflicts WHERE id=? AND status='open'
                    """,
                    (int(conflict_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to resolve legacy conflict id.") from exc
        if row is None:
            raise ValueError(f"Conflict {conflict_id} not found.")
        self.accept_manual(str(row[0]), str(row[1]), int(row[2]))

    # ---- Legacy compatibility --------------------------------------------------
    def list_track_links_for_provider(self, provider_id: str) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT source_external_id, local_file_id, track_id FROM track_links
                    WHERE source_provider_id=? ORDER BY source_external_id
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list track links for provider.") from exc
        return [
            {"source_external_id": row[0], "local_file_id": int(row[1]), "track_id": int(row[2])}
            for row in rows
        ]

    def list_local_audio_files(self) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, path, title, artists_json, album, duration_seconds, codec,
                           metadata_json, normalized_title, normalized_artists_text,
                           duration_bucket, modified_ns, updated_at
                    FROM local_audio_files ORDER BY id
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read local audio files for matching.") from exc
        return [self._local_row(row) for row in rows]

    def upsert_track(self, track: Track) -> int:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    return self._upsert_track_conn(conn, track)
        except sqlite3.Error as exc:
            raise StorageError("Failed to upsert canonical track.") from exc

    def upsert_track_link(self, link: TrackLink) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id, local_file_id,
                            confidence, match_method, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_provider_id, source_external_id, local_file_id)
                        DO UPDATE SET track_id=excluded.track_id, confidence=excluded.confidence,
                                      match_method=excluded.match_method,
                                      metadata_json=excluded.metadata_json,
                                      updated_at=datetime('now')
                        """,
                        (
                            link.track_id,
                            link.source_provider_id,
                            link.source_external_id,
                            link.local_file_id,
                            link.confidence,
                            link.match_method.value,
                            json.dumps(link.metadata_json, ensure_ascii=False),
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to upsert track link.") from exc

    def insert_conflict(self, conflict: MatchConflict) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO match_conflicts(
                            source_provider_id, source_external_id, local_file_id,
                            confidence, reason, status, score_breakdown_json,
                            candidate_rank, matcher_version, updated_at
                        ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, datetime('now'))
                        """,
                        (
                            conflict.source_provider_id,
                            conflict.source_external_id,
                            conflict.local_file_id,
                            conflict.confidence,
                            conflict.reason,
                            json.dumps(conflict.score_breakdown, ensure_ascii=False),
                            conflict.candidate_rank,
                            MATCHER_VERSION,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist matching conflict.") from exc

    def list_open_conflicts(self) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT id, source_provider_id, source_external_id, local_file_id,
                           confidence, reason, status, score_breakdown_json, candidate_rank
                    FROM match_conflicts WHERE status='open'
                    ORDER BY confidence DESC
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list open conflicts.") from exc
        return [
            {
                "id": int(row[0]),
                "source_provider_id": row[1],
                "source_external_id": row[2],
                "local_file_id": int(row[3]),
                "confidence": float(row[4]),
                "reason": row[5],
                "status": row[6],
                "breakdown": self._json_dict(row[7]),
                "rank": int(row[8] or 0),
            }
            for row in rows
        ]

    def accept_conflict(self, conflict_id: int, track_id: int | None = None) -> None:
        del track_id
        self.accept_conflict_by_id(conflict_id)

    # ---- Helpers ---------------------------------------------------------------
    @staticmethod
    def _json_dict(value: Any) -> dict[str, Any]:
        try:
            data = json.loads(value or "{}") if not isinstance(value, dict) else value
        except (json.JSONDecodeError, TypeError):
            data = {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _track_from_payload(payload: dict[str, Any]) -> Track:
        artists = tuple(str(item) for item in (payload.get("artists") or ()) if item)
        return Track(
            title=str(payload.get("title") or ""),
            artists=artists,
            album=payload.get("album_title") or payload.get("album"),
            duration_seconds=(
                float(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None
            ),
            normalized_title=normalize_text(payload.get("title")),
            normalized_artists=normalize_artists(artists),
        )

    @staticmethod
    def _upsert_track_conn(conn: sqlite3.Connection, track: Track) -> int:
        artists_json = json.dumps(track.normalized_artists, ensure_ascii=False)
        row = conn.execute(
            """
            SELECT id FROM tracks
            WHERE normalized_title=? AND normalized_artists_json=?
              AND COALESCE(album,'')=COALESCE(?, '')
            """,
            (track.normalized_title, artists_json, track.album),
        ).fetchone()
        if row:
            track_id = int(row[0])
            conn.execute(
                """
                UPDATE tracks SET title=?, artists_json=?, album=?, duration_seconds=?,
                                  updated_at=datetime('now') WHERE id=?
                """,
                (
                    track.title,
                    json.dumps(track.artists, ensure_ascii=False),
                    track.album,
                    track.duration_seconds,
                    track_id,
                ),
            )
            return track_id
        cursor = conn.execute(
            """
            INSERT INTO tracks(
                title, artists_json, album, duration_seconds,
                normalized_title, normalized_artists_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                track.title,
                json.dumps(track.artists, ensure_ascii=False),
                track.album,
                track.duration_seconds,
                track.normalized_title,
                artists_json,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _rejected_ids_conn(conn: sqlite3.Connection, provider_id: str, external_id: str) -> set[int]:
        rows = conn.execute(
            """
            SELECT local_file_id FROM match_conflicts
            WHERE source_provider_id=? AND source_external_id=? AND status='rejected'
            """,
            (provider_id, external_id),
        ).fetchall()
        return {int(row[0]) for row in rows}
