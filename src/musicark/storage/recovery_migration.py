"""Forward-only recovery/upload persistence migration for MusicArk v0.11.1."""

from __future__ import annotations


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_recovery_v0111(cursor: object) -> str:
    """Add managed-playlist, recovery history, batch and upload-mapping tables.

    The migration is additive and idempotent.  Existing Local Library, Matching,
    Coverage, Download and Sync data is never rebuilt or deleted.
    """
    row = cursor.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 9, 0):
        return current
    if parsed < (1, 8, 4):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS managed_yandex_playlists (
            provider_id TEXT NOT NULL DEFAULT 'yandex_music',
            role TEXT NOT NULL,
            playlist_kind TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider_id, role)
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_managed_yandex_playlist_kind
        ON managed_yandex_playlists(provider_id, playlist_kind)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS yandex_upload_mappings (
            local_file_id INTEGER NOT NULL,
            destination_playlist_kind TEXT NOT NULL,
            yandex_ugc_track_id TEXT,
            status TEXT NOT NULL,
            uploaded_at TEXT,
            verified_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(local_file_id, destination_playlist_kind)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_yandex_upload_mapping_track
        ON yandex_upload_mappings(destination_playlist_kind, yandex_ugc_track_id)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_track_availability_history (
            provider_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            availability_state TEXT NOT NULL DEFAULT 'unknown',
            last_known_title TEXT NOT NULL DEFAULT '',
            artists_json TEXT NOT NULL DEFAULT '[]',
            album TEXT,
            artwork_url TEXT,
            last_seen_at TEXT,
            last_available_at TEXT,
            unavailable_since TEXT,
            last_known_collections_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider_id, external_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_provider_track_availability_state
        ON provider_track_availability_history(provider_id, availability_state, updated_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS yandex_upload_batches (
            batch_id TEXT PRIMARY KEY,
            playlist_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            counts_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS yandex_upload_batch_items (
            batch_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            local_file_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'not_started',
            result_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY(batch_id, position)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_yandex_upload_batch_items_file
        ON yandex_upload_batch_items(local_file_id, batch_id)
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.9.0')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.9.0"
