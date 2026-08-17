"""Forward-only content-label migration (schema 1.8.2 -> 1.8.3)."""

from __future__ import annotations


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_content_labels_v083(cursor: object) -> str:
    """Add app-level ORIGINAL/CENSORED labels without touching audio files."""
    row = cursor.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 8, 3):
        return current
    if parsed < (1, 8, 2):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS local_track_content_labels (
            local_file_id INTEGER PRIMARY KEY,
            label TEXT NOT NULL CHECK(label IN ('original', 'censored')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_track_content_labels (
            provider_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            label TEXT NOT NULL CHECK(label IN ('original', 'censored')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider_id, external_id)
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.8.3')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.8.3"
