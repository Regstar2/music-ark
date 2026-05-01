"""Forward-only SQLite schema migrations for desktop MVP (v1.0).

Reads/writes ``app_metadata.schema_version``.
"""

from __future__ import annotations

from typing import Callable

_SCHEMA_KEY = "schema_version"

# Semantic versions applied in ascending order once when the stored version is strictly older.
MigrationFn = Callable[[object], None]  # sqlite3.Connection

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
