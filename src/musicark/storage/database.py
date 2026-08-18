"""SQLite storage bootstrap for MusicArk."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import time

from musicark.core.errors import StorageError
from musicark.storage.content_label_migration import migrate_content_labels_v083
from musicark.storage.coverage_migration import migrate_coverage_v06
from musicark.storage.download_migration import migrate_download_v07
from musicark.storage.metadata_migration import migrate_metadata_v081
from musicark.storage.metadata_editor_migration import migrate_metadata_editor_v082
from musicark.storage.migrations import ensure_schema_version_seed, migrate_schema
from musicark.storage.sync_migration import migrate_sync_v08
from musicark.storage.variant_acceptance_migration import migrate_variant_acceptance_v084


CURRENT_SCHEMA_VERSION = "1.8.4"
_DATABASE_LOCK_TIMEOUT_SECONDS = 10.0
_DATABASE_BUSY_RETRY_DELAYS = (0.25,)

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
    CREATE TABLE IF NOT EXISTS local_audio_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        sha256 TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        duration_seconds REAL,
        codec TEXT NOT NULL,
        metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS download_tasks (
        id TEXT PRIMARY KEY,
        task_type TEXT NOT NULL,
        source_id TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        status TEXT NOT NULL,
        progress REAL NOT NULL DEFAULT 0,
        target_folder TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error_message TEXT,
        result_local_file_id INTEGER,
        raw_payload_json TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artists_json TEXT NOT NULL,
        album TEXT,
        duration_seconds REAL,
        normalized_title TEXT NOT NULL,
        normalized_artists_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS track_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        source_provider_id TEXT NOT NULL,
        source_external_id TEXT NOT NULL,
        local_file_id INTEGER NOT NULL,
        confidence REAL NOT NULL,
        match_method TEXT NOT NULL,
        metadata_json TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(source_provider_id, source_external_id, local_file_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS match_conflicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_provider_id TEXT NOT NULL,
        source_external_id TEXT NOT NULL,
        local_file_id INTEGER NOT NULL,
        confidence REAL NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_plans (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        dry_run INTEGER NOT NULL DEFAULT 1,
        summary_json TEXT,
        status TEXT NOT NULL DEFAULT 'planned'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT NOT NULL,
        operation_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        confidence REAL NOT NULL,
        is_dangerous INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT
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


def _schema_is_current(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT value FROM app_metadata WHERE key='schema_version'"
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).casefold():
            return False
        raise
    return bool(row and str(row[0]) == CURRENT_SCHEMA_VERSION)


def _initialize_once(database_path: Path) -> None:
    with closing(
        sqlite3.connect(database_path, timeout=_DATABASE_LOCK_TIMEOUT_SECONDS)
    ) as conn:
        # Most bridge commands only need an already-current database. Keeping
        # this path read-only avoids unnecessary schema-lock contention between
        # short-lived Flutter bridge processes.
        if _schema_is_current(conn):
            return

        # Acquire the writer slot before migration work. If another process is
        # migrating at the same time, SQLite waits here instead of failing in
        # the middle of a forward-only migration transaction.
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _schema_is_current(conn):
                conn.commit()
                return
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            ensure_schema_version_seed(conn)
            migrate_schema(conn)
            migrate_coverage_v06(conn)
            migrate_download_v07(conn)
            migrate_sync_v08(conn)
            migrate_metadata_v081(conn)
            migrate_metadata_editor_v082(conn)
            migrate_content_labels_v083(conn)
            migrate_variant_acceptance_v084(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _is_transient_busy_error(exc: sqlite3.Error) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).casefold()
    return "locked" in message or "busy" in message


def initialize_database(database_path: Path) -> None:
    """Create SQLite file and apply all forward-only migrations idempotently.

    A short-lived lock held by another MusicArk bridge process is retried once.
    Non-locking SQLite failures still fail immediately.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    retry_delays = (*_DATABASE_BUSY_RETRY_DELAYS, None)
    for retry_delay in retry_delays:
        try:
            _initialize_once(database_path)
            return
        except sqlite3.Error as exc:
            if retry_delay is not None and _is_transient_busy_error(exc):
                time.sleep(retry_delay)
                continue
            raise StorageError(
                f"Failed to initialize SQLite DB at '{database_path}'."
            ) from exc
