"""Forward-only SQLite schema migrations for MusicArk desktop data."""

from __future__ import annotations

from typing import Callable

_SCHEMA_KEY = "schema_version"
MigrationFn = Callable[[object], None]

_SNAPSHOT_COLUMNS = {"provider_id", "collection_id", "account_json", "item_count", "refreshed_at"}
_ITEM_COLUMNS = {"provider_id", "collection_id", "external_id", "position", "payload_json"}


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
    snapshot_columns = _table_columns(c, "provider_collection_snapshots")
    item_columns = _table_columns(c, "provider_collection_items")
    if snapshot_columns and not _SNAPSHOT_COLUMNS.issubset(snapshot_columns):
        c.execute("DROP TABLE provider_collection_snapshots")
    if item_columns and not _ITEM_COLUMNS.issubset(item_columns):
        c.execute("DROP TABLE provider_collection_items")
    _create_persistent_library_tables(c)


def _add_snapshot_column(c: object, name: str, declaration: str) -> None:
    if name not in _table_columns(c, "provider_collection_snapshots"):
        c.execute(f"ALTER TABLE provider_collection_snapshots ADD COLUMN {name} {declaration}")


def _upgrade_collection_metadata(c: object) -> None:
    _create_persistent_library_tables(c)
    _add_snapshot_column(c, "collection_type", "TEXT NOT NULL DEFAULT 'liked'")
    _add_snapshot_column(c, "external_id", "TEXT")
    _add_snapshot_column(c, "title", "TEXT")
    _add_snapshot_column(c, "owner_name", "TEXT")
    _add_snapshot_column(c, "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
    _add_snapshot_column(c, "source_position", "INTEGER NOT NULL DEFAULT 0")
    _add_snapshot_column(c, "active", "INTEGER NOT NULL DEFAULT 1")
    _add_snapshot_column(c, "content_refreshed_at", "TEXT")
    c.execute(
        """
        UPDATE provider_collection_snapshots
        SET collection_type='liked', content_refreshed_at=COALESCE(content_refreshed_at, refreshed_at)
        WHERE collection_id='liked'
        """
    )
    c.execute(
        """
        UPDATE provider_collection_snapshots
        SET collection_type='playlist', external_id=COALESCE(external_id, substr(collection_id, 10))
        WHERE collection_id LIKE 'playlist:%'
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_provider_collections_type_position
        ON provider_collection_snapshots(provider_id, collection_type, active, source_position)
        """
    )


def _add_local_column(c: object, name: str, declaration: str) -> None:
    if name not in _table_columns(c, "local_audio_files"):
        c.execute(f"ALTER TABLE local_audio_files ADD COLUMN {name} {declaration}")


def _normalize_legacy_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").casefold()


def _upgrade_local_library(c: object) -> None:
    """Add v0.4 roots + incremental scan fields without touching Yandex cache."""
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS local_library_roots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            normalized_path TEXT NOT NULL UNIQUE,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_scanned_at TEXT
        )
        """
    )
    for name, declaration in (
        ("library_root_id", "INTEGER"),
        ("normalized_path", "TEXT"),
        ("file_name", "TEXT"),
        ("extension", "TEXT"),
        ("modified_ns", "INTEGER"),
        ("title", "TEXT"),
        ("artists_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("album", "TEXT"),
        ("album_artist", "TEXT"),
        ("track_number", "INTEGER"),
        ("disc_number", "INTEGER"),
        ("year", "INTEGER"),
        ("genre", "TEXT"),
        ("bitrate", "INTEGER"),
        ("sample_rate", "INTEGER"),
        ("availability", "TEXT NOT NULL DEFAULT 'available'"),
        ("last_seen_at", "TEXT"),
    ):
        _add_local_column(c, name, declaration)

    rows = c.execute("SELECT id, path, normalized_path FROM local_audio_files ORDER BY id").fetchall()
    seen: dict[str, int] = {}
    for file_id, path, current_normalized in rows:
        normalized = str(current_normalized or _normalize_legacy_path(str(path)))
        if normalized in seen:
            c.execute("DELETE FROM local_audio_files WHERE id=?", (file_id,))
            continue
        seen[normalized] = int(file_id)
        c.execute(
            """
            UPDATE local_audio_files
            SET normalized_path=?,
                file_name=COALESCE(file_name, path),
                extension=COALESCE(extension, ''),
                availability=CASE WHEN library_root_id IS NULL THEN 'legacy' ELSE availability END
            WHERE id=?
            """,
            (normalized, file_id),
        )

    c.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_local_audio_files_normalized_path
        ON local_audio_files(normalized_path)
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_local_audio_files_root_available
        ON local_audio_files(library_root_id, availability)
        """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_local_audio_files_title
        ON local_audio_files(title COLLATE NOCASE)
        """
    )


MIGRATION_STEPS: list[tuple[str, tuple[MigrationFn, ...]]] = [
    (
        "1.0.0",
        (
            lambda c: c.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC)"
            ),
        ),
    ),
    ("1.1.0", (_create_persistent_library_tables,)),
    ("1.1.1", (_repair_persistent_library_tables,)),
    ("1.2.0", (_upgrade_collection_metadata,)),
    ("1.3.0", (_upgrade_local_library,)),
]


def _parse_version(version: str) -> tuple[int, int, int]:
    parts = (version.strip() + ".0.0").split(".")[:3]
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        return (0, 0, 0)


def _read_schema_version(cursor: object) -> str:
    row = cursor.execute("SELECT value FROM app_metadata WHERE key=?", (_SCHEMA_KEY,)).fetchone()
    return str(row[0]) if row and row[0] is not None else "0.0.0"


def _write_schema_version(cursor: object, version: str) -> None:
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (_SCHEMA_KEY, version),
    )


def migrate_schema(cursor: object) -> str:
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
    row = cursor.execute("SELECT 1 FROM app_metadata WHERE key=?", (_SCHEMA_KEY,)).fetchone()
    if row is None:
        _write_schema_version(cursor, "0.1.0")
