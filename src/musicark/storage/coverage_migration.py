"""Forward-only v0.6 storage migration.

Kept isolated so the v0.6 coverage feature can be added without rewriting the
historical migration sequence. initialize_database() invokes this after the
existing migration chain.
"""

from __future__ import annotations


def migrate_coverage_v06(cursor: object) -> str:
    row = cursor.execute(
        "SELECT value FROM app_metadata WHERE key='schema_version'"
    ).fetchone()
    current = str(row[0]) if row and row[0] is not None else "0.0.0"

    def parse(value: str) -> tuple[int, int, int]:
        parts = (value.strip() + ".0.0").split(".")[:3]
        try:
            return int(parts[0]), int(parts[1]), int(parts[2])
        except (TypeError, ValueError):
            return 0, 0, 0

    if parse(current) >= (1, 6, 0):
        return current

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS provider_track_actions (
            provider_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('wanted', 'ignored')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider_id, external_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_provider_track_actions_action
        ON provider_track_actions(provider_id, action, external_id)
        """
    )
    cursor.execute(
        """
        INSERT INTO app_metadata(key, value) VALUES('schema_version', '1.6.0')
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """
    )
    return "1.6.0"
