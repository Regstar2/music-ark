"""Explicit provider/local identity binding for user-confirmed metadata imports."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.matching.fingerprints import local_file_fingerprint, provider_fingerprint
from musicark.matching.models import Track
from musicark.matching.normalize import normalize_artists, normalize_text
from musicark.matching.policy import MATCHER_VERSION
from musicark.storage.matching_storage import MatchingStorageRepository


class ExplicitIdentityService:
    """Persist only identities the user explicitly confirmed in Compare."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._matching = MatchingStorageRepository(database_path)

    def cache_provider_track(self, external_id: str, payload: dict[str, Any]) -> None:
        """Persist a safe Track snapshot so normal result/coverage queries can resolve it."""
        identity = str(external_id).strip()
        if not identity:
            raise ValueError("Yandex Track ID is required.")
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO provider_tracks(provider_id, external_id, payload_json)
                    VALUES ('yandex_music', ?, ?)
                    ON CONFLICT(provider_id, external_id) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        updated_at=datetime('now')
                    """,
                    (identity, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
                )

    @staticmethod
    def _track(payload: dict[str, Any]) -> Track:
        title = str(payload.get("title") or "").strip()
        artists_raw = payload.get("artists") or []
        artists = tuple(str(item).strip() for item in artists_raw if str(item).strip()) if isinstance(artists_raw, list) else ()
        album = payload.get("album_title") or payload.get("album")
        duration = payload.get("duration_seconds")
        try:
            duration_value = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_value = None
        return Track(
            title=title,
            artists=artists,
            album=str(album).strip() if album else None,
            duration_seconds=duration_value,
            normalized_title=normalize_text(title),
            normalized_artists=normalize_artists(artists),
        )

    def bind_yandex(
        self,
        *,
        external_id: str,
        local_file_id: int,
        provider_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create EXACT_ID=1.0 with reason=user_confirmed; never called by fuzzy matching."""
        identity = str(external_id).strip()
        file_id = int(local_file_id)
        if not identity:
            raise ValueError("Yandex Track ID is required.")
        self.cache_provider_track(identity, provider_payload)
        track_id = self._matching.upsert_track(self._track(provider_payload))
        provider_fp = provider_fingerprint("yandex_music", identity, provider_payload)

        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                local = conn.execute(
                    """
                    SELECT id, path, file_size, modified_ns, title, artists_json,
                           album, duration_seconds, codec
                    FROM local_audio_files
                    WHERE id=? AND availability='available'
                    """,
                    (file_id,),
                ).fetchone()
                if local is None:
                    raise ValueError(f"Local file {file_id} was not found.")
                local_fp = local_file_fingerprint(tuple(local[1:]))

                # One physical file cannot be user-confirmed as two different Yandex tracks.
                previous = conn.execute(
                    """
                    SELECT source_external_id FROM track_links
                    WHERE source_provider_id='yandex_music' AND local_file_id=?
                      AND match_method='exact_id' AND source_external_id<>?
                    """,
                    (file_id, identity),
                ).fetchall()
                for (old_external_id,) in previous:
                    conn.execute(
                        "DELETE FROM track_links WHERE source_provider_id='yandex_music' AND source_external_id=? AND local_file_id=?",
                        (old_external_id, file_id),
                    )
                    conn.execute(
                        """
                        UPDATE matching_results
                        SET status='unmatched', local_file_id=NULL, confidence=0,
                            method='automatic', score_breakdown_json='{}',
                            reason='user_rebound_local_file', manual=0,
                            local_fingerprint='', updated_at=datetime('now')
                        WHERE provider_id='yandex_music' AND external_id=?
                          AND local_file_id=?
                        """,
                        (old_external_id, file_id),
                    )

                conn.execute(
                    "DELETE FROM track_links WHERE source_provider_id='yandex_music' AND source_external_id=?",
                    (identity,),
                )
                conn.execute(
                    """
                    INSERT INTO track_links(
                        track_id, source_provider_id, source_external_id, local_file_id,
                        confidence, match_method, metadata_json
                    ) VALUES (?, 'yandex_music', ?, ?, 1.0, 'exact_id', ?)
                    """,
                    (
                        int(track_id), identity, file_id,
                        json.dumps(
                            {
                                "matcher_version": MATCHER_VERSION,
                                "user_confirmed": True,
                                "reason": "user_confirmed",
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO matching_results(
                        provider_id, external_id, status, local_file_id, confidence, method,
                        score_breakdown_json, reason, matcher_version,
                        provider_fingerprint, local_fingerprint, manual
                    ) VALUES ('yandex_music', ?, 'matched', ?, 1.0, 'exact_id',
                              '{"exact_id":1.0,"final":1.0}', 'user_confirmed', ?, ?, ?, 1)
                    ON CONFLICT(provider_id, external_id) DO UPDATE SET
                        status='matched', local_file_id=excluded.local_file_id,
                        confidence=1.0, method='exact_id',
                        score_breakdown_json=excluded.score_breakdown_json,
                        reason='user_confirmed', matcher_version=excluded.matcher_version,
                        provider_fingerprint=excluded.provider_fingerprint,
                        local_fingerprint=excluded.local_fingerprint,
                        manual=1, updated_at=datetime('now')
                    """,
                    (identity, file_id, MATCHER_VERSION, provider_fp, local_fp),
                )
                conn.execute(
                    """
                    UPDATE match_conflicts
                    SET status=CASE WHEN local_file_id=? THEN 'accepted' ELSE 'superseded' END,
                        updated_at=datetime('now')
                    WHERE source_provider_id='yandex_music' AND source_external_id=? AND status='open'
                    """,
                    (file_id, identity),
                )
                conn.execute(
                    """
                    UPDATE local_audio_files
                    SET source_provider_id='yandex_music', source_external_id=?, updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (identity, file_id),
                )
        return {
            "status": "matched",
            "method": "exact_id",
            "confidence": 1.0,
            "reason": "user_confirmed",
            "providerId": "yandex_music",
            "externalId": identity,
            "localFileId": file_id,
        }
