"""Forward-only v0.8 Controlled Sync migration (schema 1.7.0 -> 1.8.0)."""

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


def migrate_sync_v08(cursor: object) -> str:
    """Extend legacy sync tables in place while preserving all historical rows."""
    row = cursor.execute(
        "SELECT value FROM app_metadata WHERE key='schema_version'"
    ).fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"
    if _parse(current) >= (1, 8, 0):
        return current

    for name, declaration in (
        ("planner_version", "INTEGER NOT NULL DEFAULT 0"),
        ("scope_type", "TEXT NOT NULL DEFAULT 'legacy'"),
        ("scope_id", "TEXT"),
        ("target_root_id", "INTEGER"),
        ("target_folder", "TEXT"),
        ("input_fingerprint", "TEXT NOT NULL DEFAULT ''"),
        ("applied_at", "TEXT"),
        ("result_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("updated_at", "TEXT"),
    ):
        _add_column(cursor, "sync_plans", name, declaration)

    for name, declaration in (
        ("status", "TEXT NOT NULL DEFAULT 'informational'"),
        ("result_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("updated_at", "TEXT"),
    ):
        _add_column(cursor, "sync_operations", name, declaration)

    cursor.execute(
        """
        UPDATE sync_plans
        SET planner_version=COALESCE(planner_version, 0),
            scope_type=COALESCE(NULLIF(scope_type, ''), 'legacy'),
            input_fingerprint=COALESCE(input_fingerprint, ''),
            result_json=COALESCE(result_json, '{}'),
            updated_at=COALESCE(updated_at, applied_at, created_at, datetime('now'))
        """
    )
    cursor.execute(
        """
        UPDATE sync_operations
        SET status=COALESCE(NULLIF(status, ''), 'informational'),
            result_json=COALESCE(result_json, '{}'),
            updated_at=COALESCE(updated_at, datetime('now'))
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sync_plans_status_created
        ON sync_plans(status, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sync_operations_plan_status
        ON sync_operations(plan_id, status, id)
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.8.0')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.8.0"
