"""Forward-only v0.8.1 local provenance migration (schema 1.8.0 -> 1.8.1)."""

from __future__ import annotations


def _columns(cursor: object, table: str) -> set[str]:
    return {str(row[1]) for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(cursor: object, table: str, name: str, declaration: str) -> None:
    if name not in _columns(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_metadata_v081(cursor: object) -> str:
    """Persist trusted embedded provider identity without changing user audio files."""
    row = cursor.execute(
        "SELECT value FROM app_metadata WHERE key='schema_version'"
    ).fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    parsed = _parse(current)
    if parsed >= (1, 8, 1):
        return current
    if parsed < (1, 8, 0):
        # The bootstrap calls this only after v0.8 migrations. Never jump over
        # missing historical migrations when invoked independently.
        return current

    _add_column(cursor, "local_audio_files", "source_provider_id", "TEXT")
    _add_column(cursor, "local_audio_files", "source_external_id", "TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_local_audio_files_source_identity
        ON local_audio_files(source_provider_id, source_external_id)
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.8.1')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.8.1"
