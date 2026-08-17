"""Forward-only metadata editor/artwork cache migration (schema 1.8.1 -> 1.8.2)."""

from __future__ import annotations


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_metadata_editor_v082(cursor: object) -> str:
    """Add only cache state; user audio remains outside SQLite migration writes."""
    row = cursor.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 8, 2):
        return current
    if parsed < (1, 8, 1):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS local_artwork_cache (
            local_file_id INTEGER PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            cache_path TEXT NOT NULL,
            source TEXT NOT NULL,
            mime TEXT,
            width INTEGER,
            height INTEGER,
            byte_size INTEGER,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.8.2')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.8.2"
