"""Forward-only v0.7 download queue migration (schema 1.6.0 -> 1.7.0)."""

from __future__ import annotations


def _columns(cursor: object, table: str) -> set[str]:
    return {str(row[1]) for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_column(cursor: object, name: str, declaration: str) -> None:
    if name not in _columns(cursor, "download_tasks"):
        cursor.execute(f"ALTER TABLE download_tasks ADD COLUMN {name} {declaration}")


def _parse(value: str) -> tuple[int, int, int]:
    parts = (value.strip() + ".0.0").split(".")[:3]
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0, 0


def migrate_download_v07(cursor: object) -> str:
    """Extend the existing queue in place without replacing legacy rows."""
    row = cursor.execute(
        "SELECT value FROM app_metadata WHERE key='schema_version'"
    ).fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    if _parse(current) >= (1, 7, 0):
        return current

    for name, declaration in (
        ("downloaded_bytes", "INTEGER NOT NULL DEFAULT 0"),
        ("total_bytes", "INTEGER"),
        ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
        ("target_root_id", "INTEGER"),
        ("error_code", "TEXT"),
        ("updated_at", "TEXT"),
    ):
        _add_column(cursor, name, declaration)

    cursor.execute(
        """
        UPDATE download_tasks
        SET updated_at=COALESCE(updated_at, finished_at, started_at, created_at, datetime('now')),
            downloaded_bytes=COALESCE(downloaded_bytes, 0),
            cancel_requested=COALESCE(cancel_requested, 0)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_download_tasks_identity_status
        ON download_tasks(provider_id, source_id, status, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_download_tasks_status_updated
        ON download_tasks(status, updated_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS download_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.7.0')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.7.0"
