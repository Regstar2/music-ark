"""Forward-only external metadata persistence migration for MusicArk v0.12.0."""

from __future__ import annotations


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_external_metadata_v012(cursor: object) -> str:
    """Add external identities, response/fingerprint caches and WARP ownership state."""
    row = cursor.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 10, 0):
        return current
    if parsed < (1, 9, 0):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS local_external_identities (
            local_file_id INTEGER NOT NULL,
            identity_type TEXT NOT NULL,
            identity_value TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'possible',
            user_confirmed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(local_file_id, identity_type, identity_value)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_local_external_identity_value
        ON local_external_identities(identity_type, identity_value)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_audio_fingerprints (
            local_file_id INTEGER PRIMARY KEY,
            file_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_metadata_cache (
            cache_key TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            negative INTEGER NOT NULL DEFAULT 0,
            expires_at TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_metadata_cache_expiry
        ON external_metadata_cache(provider_id, expires_at)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS external_artwork_cache (
            artwork_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            cache_path TEXT NOT NULL,
            mime TEXT,
            byte_size INTEGER,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS network_component_state (
            component_id TEXT PRIMARY KEY,
            installed_by_musicark INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.10.0')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.10.0"
