"""Forward-only user variant-acceptance migration (schema 1.8.3 -> 1.8.4)."""

from __future__ import annotations


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_variant_acceptance_v084(cursor: object) -> str:
    """Persist explicit acceptance of a reviewed local recording variant."""
    row = cursor.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 8, 4):
        return current
    if parsed < (1, 8, 3):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS variant_user_acceptance (
            provider_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            local_file_id INTEGER NOT NULL,
            variant_status TEXT NOT NULL,
            provider_variant_fingerprint TEXT NOT NULL DEFAULT '',
            local_audio_fingerprint TEXT NOT NULL DEFAULT '',
            reference_audio_fingerprint TEXT NOT NULL DEFAULT '',
            analyzer_version INTEGER NOT NULL DEFAULT 0,
            analysis_updated_at TEXT,
            accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider_id, external_id, local_file_id)
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.8.4')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.8.4"
