"""SQLite storage bootstrap for v0.1 core foundation."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from musicark.core.errors import StorageError


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS providers (
        provider_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        capabilities_json TEXT NOT NULL,
        metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS track_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        external_id TEXT NOT NULL,
        url TEXT,
        availability TEXT,
        raw_data_json TEXT,
        first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(provider_id, external_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL,
        external_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(provider_id, external_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL,
        external_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(provider_id, external_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_raw_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL,
        response_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        status TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
)


def initialize_database(database_path: Path) -> None:
    """Create SQLite file and minimal schema for core modules."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            with conn:
                for statement in SCHEMA_STATEMENTS:
                    conn.execute(statement)
                conn.execute(
                    """
                    INSERT INTO app_metadata(key, value)
                    VALUES('schema_version', '0.3.0')
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value;
                    """
                )
    except sqlite3.Error as exc:
        raise StorageError(f"Failed to initialize SQLite DB at '{database_path}'.") from exc
