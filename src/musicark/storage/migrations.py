"""Forward-only SQLite schema migrations for MusicArk desktop data."""

from __future__ import annotations

from typing import Callable

_SCHEMA_KEY = "schema_version"
MigrationFn = Callable[[object], None]  # sqlite3.Connection

_SNAPSHOT_COLUMNS = {
    "provider_id",
    "collection_id",
    "account_json",
    "item_count",
    "refreshed_at",
}
_ITEM_COLUMNS = {
    "provider_id",
    "collection_id",
    "external_id",
    "position",
    "payload_json",
}


def _table_columns(c: object, table_name: str) -> set[str]:
    rows = c.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _create_persistent_library_tables(c: object) -> None:
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_collection_snapshots (
            provider_id TEXT NOT NULL,
            collection_id TEXT NOT NULL,
            account_json TEXT NOT NULL DEFAULT '{}',
            item_count INTEGER NOT NULL DEFAULT 0,
            refreshed_at TEXT NOT NULL,
            PRIMARY KEY(provider_id, collection_id)
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_collection_items (
            provider_id TEXT NOT NULL,
            collection_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY(provider_id, collection_id, external_id)
        )
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_provider_collection_items_position
        ON provider_collection_items(provider_id, collection_id, position)
        """
    )


def _repair_persistent_library_tables(c: object) -> None:
    """Repair cache-only tables created by older experimental local schemas.

    These tables contain rebuildable provider cache data only. If an older
    local experiment created a table with the same name but incompatible
    columns, preserving it would make the v0.2 INSERT statements fail forever.
    """
    snapshot_columns = _table_columns(c, "provider_collection_snapshots")
    item_columns = _table_columns(c, "provider_collection_items")

    if snapshot_columns and not _SNAPSHOT_COLUMNS.issubset(snapshot_columns):
        c.execute("DROP TABLE provider_collection_snapshots")
    if item_columns and not _ITEM_COLUMNS.issubset(item_columns):
        c.execute("DROP TABLE provider_collection_items")

    _create_persistent_library_tables(c)


MIGRATION_STEPS: list[tuple[str, tuple[MigrationFn, ...]]] = [
    (
        "1.0.0",
        (
            lambda c: c.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
                ON audit_log(created_at DESC)
                """
            ),
        ),
    ),
    (
        "1.1.0",
        (_create_persistent_library_tables,),
    ),
    (
        "1.1.1",
        (_repair_persistent_library_tables,),
    ),
]


def _parse_version(version: str) -> tuple[int, int, int]:
    parts = (version.strip() + ".0.0").split(".")[:3]
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        return (0, 0, 0)


def _read_schema_version(cursor: object) -> str:
    row = cursor.execute(
        "SELECT value FROM app_metadata WHERE key=?",
        (_SCHEMA_KEY,),
    ).fetchone()
    return str(row[0]) if row and row[0] is not None else "0.0.0"


def _write_schema_version(cursor: object, version: str) -> None:
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (_SCHEMA_KEY, version),
    )


def migrate_schema(cursor: object) -> str:
    """Apply pending migrations. ``cursor`` must be inside an active transaction."""
    current_raw = _read_schema_version(cursor)
    current_tuple = _parse_version(current_raw)
    last_version = current_raw
    for target_version, steps in sorted(MIGRATION_STEPS, key=lambda x: _parse_version(x[0])):
        if _parse_version(target_version) <= current_tuple:
            continue
        for step in steps:
            step(cursor)
        _write_schema_version(cursor, target_version)
        current_tuple = _parse_version(target_version)
        last_version = target_version
    return last_version


def ensure_schema_version_seed(cursor: object) -> None:
    """Bootstrap schema_version row for databases created before migration runner existed."""
    row = cursor.execute(
        "SELECT 1 FROM app_metadata WHERE key=?",
        (_SCHEMA_KEY,),
    ).fetchone()
    if row is None:
        _write_schema_version(cursor, "0.1.0")
