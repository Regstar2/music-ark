"""SQLite persistence/query boundary for v0.5.1 variant analysis."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.errors import StorageError
from .models import AlteredRegion, VariantResult, VariantStatus


def _json_object(value: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _json_list(value: str | None) -> list[Any]:
    try:
        decoded = json.loads(value or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return decoded if isinstance(decoded, list) else []


class VariantStorageRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def matched_pair(self, provider_id: str, external_id: str) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT mr.provider_id, mr.external_id, mr.status, mr.local_file_id,
                           mr.confidence, mr.method, mr.manual, pt.payload_json,
                           laf.path, laf.file_size, laf.modified_ns, laf.duration_seconds,
                           laf.title, laf.artists_json, laf.album, laf.metadata_json,
                           laf.availability, laf.updated_at
                    FROM matching_results mr
                    JOIN provider_tracks pt
                      ON pt.provider_id=mr.provider_id AND pt.external_id=mr.external_id
                    LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                    WHERE mr.provider_id=? AND mr.external_id=?
                    LIMIT 1
                    """,
                    (provider_id, external_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load variant candidate pair.") from exc
        if row is None or str(row[2]) != "matched" or row[3] is None:
            return None
        try:
            artists = json.loads(row[13] or "[]")
        except (json.JSONDecodeError, TypeError):
            artists = []
        provider = _json_object(row[7])
        local_metadata = _json_object(row[15])
        return {
            "providerId": str(row[0]),
            "externalId": str(row[1]),
            "identityStatus": str(row[2]),
            "identityConfidence": float(row[4] or 0.0),
            "identityMethod": str(row[5] or ""),
            "manual": bool(row[6]),
            "provider": provider,
            "local": {
                "id": int(row[3]),
                "path": str(row[8] or ""),
                "file_size": int(row[9] or 0),
                "modified_ns": int(row[10] or 0),
                "duration_seconds": row[11],
                "durationSeconds": row[11],
                "title": row[12],
                "artists": artists if isinstance(artists, list) else [],
                "album": row[14],
                "metadata": local_metadata,
                "availability": row[16],
                "updatedAt": row[17],
            },
        }

    def list_matched_pairs(self, provider_id: str) -> list[dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                identities = conn.execute(
                    """
                    SELECT external_id
                    FROM matching_results
                    WHERE provider_id=? AND status='matched' AND local_file_id IS NOT NULL
                    ORDER BY external_id
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list variant candidate pairs.") from exc
        result: list[dict[str, Any]] = []
        for (external_id,) in identities:
            pair = self.matched_pair(provider_id, str(external_id))
            if pair is not None:
                result.append(pair)
        return result

    def get(self, provider_id: str, external_id: str, local_file_id: int) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT status, metadata_score, metadata_json, audio_similarity,
                           variant_reasons_json, altered_segments_json,
                           provider_variant_fingerprint, local_audio_fingerprint,
                           reference_audio_fingerprint, analyzer_version, reference_path,
                           created_at, updated_at
                    FROM track_variant_results
                    WHERE provider_id=? AND external_id=? AND local_file_id=?
                    """,
                    (provider_id, external_id, int(local_file_id)),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to load variant result.") from exc
        if row is None:
            return None
        return {
            "providerId": provider_id,
            "externalId": external_id,
            "localFileId": int(local_file_id),
            "status": str(row[0]),
            "variantStatus": str(row[0]),
            "metadataScore": row[1],
            "metadata": _json_object(row[2]),
            "audioSimilarity": row[3],
            "variantReasons": [str(item) for item in _json_list(row[4])],
            "alteredSegments": _json_list(row[5]),
            "providerVariantFingerprint": str(row[6] or ""),
            "localAudioFingerprint": str(row[7] or ""),
            "referenceAudioFingerprint": str(row[8] or ""),
            "analyzerVersion": int(row[9] or 0),
            "referencePath": row[10],
            "createdAt": row[11],
            "updatedAt": row[12],
        }

    def upsert(self, result: VariantResult) -> dict[str, Any]:
        metadata_json = json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)
        reasons_json = json.dumps(list(result.reasons), ensure_ascii=False)
        segments_json = json.dumps(
            [region.as_dict() for region in result.altered_regions],
            ensure_ascii=False,
        )
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO track_variant_results(
                            provider_id, external_id, local_file_id, status,
                            metadata_score, metadata_json, audio_similarity,
                            variant_reasons_json, altered_segments_json,
                            provider_variant_fingerprint, local_audio_fingerprint,
                            reference_audio_fingerprint, analyzer_version, reference_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_id, external_id, local_file_id) DO UPDATE SET
                            status=excluded.status,
                            metadata_score=excluded.metadata_score,
                            metadata_json=excluded.metadata_json,
                            audio_similarity=excluded.audio_similarity,
                            variant_reasons_json=excluded.variant_reasons_json,
                            altered_segments_json=excluded.altered_segments_json,
                            provider_variant_fingerprint=excluded.provider_variant_fingerprint,
                            local_audio_fingerprint=excluded.local_audio_fingerprint,
                            reference_audio_fingerprint=excluded.reference_audio_fingerprint,
                            analyzer_version=excluded.analyzer_version,
                            reference_path=excluded.reference_path,
                            updated_at=datetime('now')
                        """,
                        (
                            result.provider_id,
                            result.external_id,
                            int(result.local_file_id),
                            result.status.value,
                            result.metadata_score,
                            metadata_json,
                            result.audio_similarity,
                            reasons_json,
                            segments_json,
                            result.provider_variant_fingerprint,
                            result.local_audio_fingerprint,
                            result.reference_audio_fingerprint,
                            int(result.analyzer_version),
                            result.reference_path,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist variant result.") from exc
        saved = self.get(result.provider_id, result.external_id, result.local_file_id)
        if saved is None:  # pragma: no cover - defensive storage invariant.
            raise StorageError("Variant result was not persisted.")
        return saved

    def list_results(
        self,
        provider_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
        status: str = "",
    ) -> dict[str, Any]:
        page_limit = max(1, min(int(limit), 1000))
        page_offset = max(0, int(offset))
        where = ["tvr.provider_id=?"]
        params: list[Any] = [provider_id]
        valid_statuses = {item.value for item in VariantStatus}
        if status in valid_statuses:
            where.append("tvr.status=?")
            params.append(status)
        where_sql = " AND ".join(where)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM track_variant_results tvr WHERE {where_sql}",
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    f"""
                    SELECT tvr.external_id, tvr.local_file_id
                    FROM track_variant_results tvr
                    WHERE {where_sql}
                    ORDER BY tvr.updated_at DESC, tvr.external_id
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_limit, page_offset],
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to list variant results.") from exc
        items = [
            self.get(provider_id, str(external_id), int(local_file_id))
            for external_id, local_file_id in rows
        ]
        return {
            "count": total,
            "limit": page_limit,
            "offset": page_offset,
            "items": [item for item in items if item is not None],
        }

    def summary(self, provider_id: str) -> dict[str, Any]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                matched = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM matching_results
                        WHERE provider_id=? AND status='matched' AND local_file_id IS NOT NULL
                        """,
                        (provider_id,),
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM track_variant_results
                    WHERE provider_id=?
                    GROUP BY status
                    """,
                    (provider_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to summarize variant results.") from exc
        counts = {item.value: 0 for item in VariantStatus}
        for status, count in rows:
            if str(status) in counts:
                counts[str(status)] = int(count)
        checked = sum(count for status, count in counts.items() if status != VariantStatus.NOT_CHECKED.value)
        return {
            "providerId": provider_id,
            "eligibleMatched": matched,
            "stored": sum(counts.values()),
            "checked": checked,
            "same": counts[VariantStatus.SAME.value],
            "altered": counts[VariantStatus.ALTERED.value],
            "differentVersion": counts[VariantStatus.DIFFERENT_VERSION.value],
            "uncertain": counts[VariantStatus.UNCERTAIN.value],
            "notChecked": max(counts[VariantStatus.NOT_CHECKED.value], matched - sum(counts.values())),
        }


def regions_from_dicts(items: list[dict[str, Any]]) -> tuple[AlteredRegion, ...]:
    regions: list[AlteredRegion] = []
    for item in items:
        try:
            regions.append(
                AlteredRegion(
                    start_seconds=float(item.get("startSeconds", 0.0)),
                    end_seconds=float(item.get("endSeconds", 0.0)),
                    mean_similarity=float(item.get("meanSimilarity", 0.0)),
                    minimum_similarity=float(item.get("minimumSimilarity", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(regions)
