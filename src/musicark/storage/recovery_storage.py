"""SQLite persistence for v0.11.1 recovery, managed playlists and upload batches."""

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from musicark.core.errors import StorageError
from musicark.storage.database import initialize_database

_PROVIDER_ID = "yandex_music"
_VALID_ROLES = frozenset({"censored", "uploaded", "unavailable"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _json_dict(value: object) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(decoded) if isinstance(decoded, dict) else {}


def _json_list(value: object) -> list[Any]:
    try:
        decoded = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    return list(decoded) if isinstance(decoded, list) else []


class RecoveryStorageRepository:
    """Small additive repository; no raw provider responses or filesystem paths are stored here."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = Path(database_path)
        initialize_database(self._database_path)

    # ---- managed playlists -------------------------------------------------
    def managed_playlists(self) -> dict[str, dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT role, playlist_kind, title, updated_at
                    FROM managed_yandex_playlists
                    WHERE provider_id=?
                    ORDER BY role
                    """,
                    (_PROVIDER_ID,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read managed Yandex playlists.") from exc
        return {
            str(role): {
                "role": str(role),
                "playlistKind": str(kind),
                "title": str(title or ""),
                "updatedAt": str(updated_at or ""),
            }
            for role, kind, title, updated_at in rows
        }

    def set_managed_playlist(self, role: str, playlist_kind: str, title: str) -> None:
        clean_role = str(role).strip().casefold()
        if clean_role not in _VALID_ROLES:
            raise ValueError("Unsupported managed playlist role.")
        kind = str(playlist_kind).strip()
        if not kind:
            raise ValueError("playlist_kind is required.")
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO managed_yandex_playlists(provider_id, role, playlist_kind, title)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(provider_id, role) DO UPDATE SET
                            playlist_kind=excluded.playlist_kind,
                            title=excluded.title,
                            updated_at=datetime('now')
                        """,
                        (_PROVIDER_ID, clean_role, kind, str(title or "")),
                    )
        except sqlite3.IntegrityError as exc:
            raise StorageError("This Yandex playlist is already assigned to another MusicArk role.") from exc
        except sqlite3.Error as exc:
            raise StorageError("Failed to save managed Yandex playlist.") from exc

    def clear_managed_playlist(self, role: str) -> None:
        clean_role = str(role).strip().casefold()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        "DELETE FROM managed_yandex_playlists WHERE provider_id=? AND role=?",
                        (_PROVIDER_ID, clean_role),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to clear managed Yandex playlist.") from exc

    # ---- upload mappings ---------------------------------------------------
    def upload_mappings(
        self, local_file_ids: Iterable[int], playlist_kind: str
    ) -> dict[int, dict[str, Any]]:
        ids = list(dict.fromkeys(int(value) for value in local_file_ids if int(value) > 0))[:5000]
        kind = str(playlist_kind).strip()
        if not ids or not kind:
            return {}
        result: dict[int, dict[str, Any]] = {}
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                for offset in range(0, len(ids), 400):
                    part = ids[offset : offset + 400]
                    marks = ",".join("?" for _ in part)
                    rows = conn.execute(
                        f"""
                        SELECT local_file_id, yandex_ugc_track_id, status, uploaded_at, verified_at, updated_at
                        FROM yandex_upload_mappings
                        WHERE destination_playlist_kind=? AND local_file_id IN ({marks})
                        """,
                        [kind, *part],
                    ).fetchall()
                    for row in rows:
                        result[int(row[0])] = {
                            "localFileId": int(row[0]),
                            "trackId": str(row[1]) if row[1] else None,
                            "status": str(row[2]),
                            "uploadedAt": str(row[3]) if row[3] else None,
                            "verifiedAt": str(row[4]) if row[4] else None,
                            "updatedAt": str(row[5]) if row[5] else None,
                        }
        except sqlite3.Error as exc:
            raise StorageError("Failed to read Yandex upload mappings.") from exc
        return result

    def upsert_upload_mapping(
        self,
        *,
        local_file_id: int,
        playlist_kind: str,
        track_id: str | None,
        status: str,
        verified: bool,
    ) -> None:
        now = _now()
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO yandex_upload_mappings(
                            local_file_id, destination_playlist_kind, yandex_ugc_track_id,
                            status, uploaded_at, verified_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(local_file_id, destination_playlist_kind) DO UPDATE SET
                            yandex_ugc_track_id=excluded.yandex_ugc_track_id,
                            status=excluded.status,
                            uploaded_at=COALESCE(yandex_upload_mappings.uploaded_at, excluded.uploaded_at),
                            verified_at=CASE
                                WHEN excluded.verified_at IS NULL THEN yandex_upload_mappings.verified_at
                                ELSE excluded.verified_at
                            END,
                            updated_at=excluded.updated_at
                        """,
                        (
                            int(local_file_id),
                            str(playlist_kind),
                            str(track_id) if track_id else None,
                            str(status),
                            now,
                            now if verified else None,
                            now,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist Yandex upload mapping.") from exc

    # ---- provider availability history ------------------------------------
    def availability_history(self) -> dict[str, dict[str, Any]]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT external_id, availability_state, last_known_title, artists_json,
                           album, artwork_url, last_seen_at, last_available_at,
                           unavailable_since, last_known_collections_json, updated_at
                    FROM provider_track_availability_history
                    WHERE provider_id=?
                    """,
                    (_PROVIDER_ID,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read provider availability history.") from exc
        return {
            str(row[0]): {
                "externalId": str(row[0]),
                "availability": str(row[1]),
                "title": str(row[2] or ""),
                "artists": [str(value) for value in _json_list(row[3])],
                "album": row[4],
                "artworkUrl": row[5],
                "lastSeenAt": row[6],
                "lastAvailableAt": row[7],
                "unavailableSince": row[8],
                "collections": _json_list(row[9]),
                "updatedAt": row[10],
            }
            for row in rows
        }

    def upsert_availability(
        self,
        *,
        external_id: str,
        availability: str,
        title: str,
        artists: list[str],
        album: str | None,
        artwork_url: str | None,
        collections: list[dict[str, Any]],
    ) -> tuple[str | None, str]:
        identity = str(external_id).strip()
        state = str(availability).strip().casefold()
        if state not in {"available", "unavailable", "unknown"}:
            state = "unknown"
        now = _now()
        previous: str | None = None
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                existing = conn.execute(
                    """
                    SELECT availability_state, unavailable_since, last_available_at
                    FROM provider_track_availability_history
                    WHERE provider_id=? AND external_id=?
                    """,
                    (_PROVIDER_ID, identity),
                ).fetchone()
                if existing:
                    previous = str(existing[0])
                    unavailable_since = existing[1]
                    last_available_at = existing[2]
                else:
                    unavailable_since = None
                    last_available_at = None
                if state == "unavailable" and previous != "unavailable":
                    unavailable_since = now
                if state == "available":
                    last_available_at = now
                    unavailable_since = None
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_track_availability_history(
                            provider_id, external_id, availability_state, last_known_title,
                            artists_json, album, artwork_url, last_seen_at, last_available_at,
                            unavailable_since, last_known_collections_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_id, external_id) DO UPDATE SET
                            availability_state=excluded.availability_state,
                            last_known_title=CASE WHEN excluded.last_known_title='' THEN provider_track_availability_history.last_known_title ELSE excluded.last_known_title END,
                            artists_json=CASE WHEN excluded.artists_json='[]' THEN provider_track_availability_history.artists_json ELSE excluded.artists_json END,
                            album=COALESCE(excluded.album, provider_track_availability_history.album),
                            artwork_url=COALESCE(excluded.artwork_url, provider_track_availability_history.artwork_url),
                            last_seen_at=excluded.last_seen_at,
                            last_available_at=excluded.last_available_at,
                            unavailable_since=excluded.unavailable_since,
                            last_known_collections_json=excluded.last_known_collections_json,
                            updated_at=excluded.updated_at
                        """,
                        (
                            _PROVIDER_ID,
                            identity,
                            state,
                            str(title or ""),
                            json.dumps([str(value) for value in artists], ensure_ascii=False),
                            album,
                            artwork_url,
                            now,
                            last_available_at,
                            unavailable_since,
                            json.dumps(collections, ensure_ascii=False, sort_keys=True),
                            now,
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to persist provider availability history.") from exc
        return previous, state

    def mark_disappeared(self, external_id: str) -> tuple[str | None, str]:
        """Membership disappearance is not proof of provider unavailability."""
        identity = str(external_id).strip()
        now = _now()
        previous: str | None = None
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT availability_state FROM provider_track_availability_history
                    WHERE provider_id=? AND external_id=?
                    """,
                    (_PROVIDER_ID, identity),
                ).fetchone()
                if row is None:
                    return None, "unknown"
                previous = str(row[0])
                with conn:
                    conn.execute(
                        """
                        UPDATE provider_track_availability_history
                        SET availability_state='unknown', updated_at=?
                        WHERE provider_id=? AND external_id=?
                        """,
                        (now, _PROVIDER_ID, identity),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to update provider availability history.") from exc
        return previous, "unknown"

    # ---- current cached playlist snapshot ---------------------------------
    def cached_playlist_memberships(self) -> dict[str, dict[str, Any]]:
        """Aggregate all cached user playlist rows in one query and deduplicate identities."""
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT s.external_id, s.title, i.payload_json
                    FROM provider_collection_snapshots s
                    JOIN provider_collection_items i
                      ON i.provider_id=s.provider_id AND i.collection_id=s.collection_id
                    WHERE s.provider_id=? AND s.collection_type='playlist' AND s.active=1
                    ORDER BY s.source_position, i.position
                    """,
                    (_PROVIDER_ID,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to aggregate cached Yandex playlists.") from exc

        result: dict[str, dict[str, Any]] = {}
        for playlist_kind, playlist_title, payload_json in rows:
            payload = _json_dict(payload_json)
            external_id = str(payload.get("external_id") or payload.get("externalId") or "").strip()
            if not external_id:
                continue
            item = result.setdefault(
                external_id,
                {
                    "externalId": external_id,
                    "title": str(payload.get("title") or ""),
                    "artists": [str(value) for value in payload.get("artists", [])]
                    if isinstance(payload.get("artists"), list)
                    else [],
                    "album": payload.get("album_title") or payload.get("album"),
                    "artworkUrl": payload.get("artwork_url") or payload.get("artworkUrl"),
                    "availabilitySignals": [],
                    "collections": [],
                },
            )
            signal = payload.get("availability")
            if signal in {"available", "unavailable"}:
                item["availabilitySignals"].append(str(signal))
            else:
                item["availabilitySignals"].append("unknown")
            membership = {
                "playlistKind": str(playlist_kind or ""),
                "title": str(playlist_title or playlist_kind or ""),
            }
            if membership not in item["collections"]:
                item["collections"].append(membership)
            if not item["title"] and payload.get("title"):
                item["title"] = str(payload["title"])
        return result

    def matching_context(self, external_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = list(dict.fromkeys(str(value).strip() for value in external_ids if str(value).strip()))[:10000]
        if not ids:
            return {}
        result: dict[str, dict[str, Any]] = {}
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                for offset in range(0, len(ids), 350):
                    part = ids[offset : offset + 350]
                    marks = ",".join("?" for _ in part)
                    rows = conn.execute(
                        f"""
                        SELECT mr.external_id, mr.status, mr.local_file_id, mr.confidence,
                               laf.file_name, laf.extension, laf.availability,
                               pcl.label, lcl.label,
                               tvr.status
                        FROM matching_results mr
                        LEFT JOIN local_audio_files laf ON laf.id=mr.local_file_id
                        LEFT JOIN provider_track_content_labels pcl
                          ON pcl.provider_id=mr.provider_id AND pcl.external_id=mr.external_id
                        LEFT JOIN local_track_content_labels lcl ON lcl.local_file_id=mr.local_file_id
                        LEFT JOIN track_variant_results tvr
                          ON tvr.provider_id=mr.provider_id
                         AND tvr.external_id=mr.external_id
                         AND tvr.local_file_id=mr.local_file_id
                        WHERE mr.provider_id=? AND mr.external_id IN ({marks})
                        """,
                        [_PROVIDER_ID, *part],
                    ).fetchall()
                    for row in rows:
                        result[str(row[0])] = {
                            "matchingStatus": str(row[1] or ""),
                            "localFileId": int(row[2]) if row[2] is not None else None,
                            "confidence": float(row[3] or 0.0),
                            "localFileName": str(row[4] or "") if row[4] is not None else None,
                            "localExtension": str(row[5] or "").casefold() if row[5] is not None else None,
                            "localAvailable": row[6] == "available",
                            "providerContentLabel": str(row[7]) if row[7] else None,
                            "localContentLabel": str(row[8]) if row[8] else None,
                            "variantStatus": str(row[9]) if row[9] else "not_checked",
                        }
        except sqlite3.Error as exc:
            raise StorageError("Failed to read recovery matching context.") from exc
        return result

    # ---- persisted batch state --------------------------------------------
    def create_batch(self, batch_id: str, playlist_kind: str, local_file_ids: list[int]) -> None:
        ids = [int(value) for value in local_file_ids]
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO yandex_upload_batches(batch_id, playlist_kind, status, total)
                        VALUES (?, ?, 'running', ?)
                        """,
                        (str(batch_id), str(playlist_kind), len(ids)),
                    )
                    conn.executemany(
                        """
                        INSERT INTO yandex_upload_batch_items(batch_id, position, local_file_id)
                        VALUES (?, ?, ?)
                        """,
                        ((str(batch_id), position, file_id) for position, file_id in enumerate(ids)),
                    )
        except sqlite3.IntegrityError as exc:
            raise StorageError("Upload batch id already exists.") from exc
        except sqlite3.Error as exc:
            raise StorageError("Failed to create upload batch state.") from exc

    def update_batch_item(
        self,
        batch_id: str,
        position: int,
        *,
        status: str,
        result: dict[str, Any],
    ) -> None:
        safe_result = dict(result)
        safe_result.pop("path", None)
        safe_result.pop("filePath", None)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        UPDATE yandex_upload_batch_items
                        SET status=?, result_json=?
                        WHERE batch_id=? AND position=?
                        """,
                        (
                            str(status),
                            json.dumps(safe_result, ensure_ascii=False, sort_keys=True),
                            str(batch_id),
                            int(position),
                        ),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to update upload batch item.") from exc

    def finish_batch(
        self,
        batch_id: str,
        *,
        status: str,
        completed: int,
        counts: dict[str, int],
    ) -> None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        UPDATE yandex_upload_batches
                        SET status=?, completed=?, counts_json=?, finished_at=datetime('now')
                        WHERE batch_id=?
                        """,
                        (str(status), int(completed), json.dumps(counts, sort_keys=True), str(batch_id)),
                    )
        except sqlite3.Error as exc:
            raise StorageError("Failed to finish upload batch.") from exc

    def request_cancel(self, batch_id: str) -> bool:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    cursor = conn.execute(
                        """
                        UPDATE yandex_upload_batches SET cancel_requested=1
                        WHERE batch_id=? AND status='running'
                        """,
                        (str(batch_id),),
                    )
                    return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise StorageError("Failed to cancel upload batch.") from exc

    def cancel_requested(self, batch_id: str) -> bool:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    "SELECT cancel_requested FROM yandex_upload_batches WHERE batch_id=?",
                    (str(batch_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read upload batch cancellation state.") from exc
        return bool(row and int(row[0]) == 1)

    def batch(self, batch_id: str) -> dict[str, Any] | None:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                row = conn.execute(
                    """
                    SELECT playlist_kind, status, total, completed, cancel_requested,
                           counts_json, created_at, finished_at
                    FROM yandex_upload_batches WHERE batch_id=?
                    """,
                    (str(batch_id),),
                ).fetchone()
                if row is None:
                    return None
                item_rows = conn.execute(
                    """
                    SELECT position, local_file_id, status, result_json
                    FROM yandex_upload_batch_items WHERE batch_id=? ORDER BY position
                    """,
                    (str(batch_id),),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError("Failed to read upload batch state.") from exc
        return {
            "batchId": str(batch_id),
            "playlistKind": str(row[0]),
            "status": str(row[1]),
            "total": int(row[2]),
            "completed": int(row[3]),
            "cancelRequested": bool(row[4]),
            "counts": {str(k): int(v) for k, v in _json_dict(row[5]).items()},
            "createdAt": str(row[6]),
            "finishedAt": str(row[7]) if row[7] else None,
            "items": [
                {
                    "position": int(item[0]),
                    "localFileId": int(item[1]),
                    "status": str(item[2]),
                    "result": _json_dict(item[3]),
                }
                for item in item_rows
            ],
        }
