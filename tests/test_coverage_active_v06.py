from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.coverage.service import LibraryCoverageService
from musicark.storage.database import initialize_database


class CoverageActiveDatasetV06Tests(unittest.TestCase):
    def test_inactive_snapshot_hides_leftover_membership_and_rejects_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / ".musicark" / "musicark.db"
            initialize_database(db)
            payload = {
                "provider_id": "yandex_music",
                "external_id": "9",
                "title": "Removed track",
                "artists": ["Artist"],
                "album_title": "Album",
                "duration_seconds": 180.0,
            }
            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    INSERT INTO provider_collection_snapshots(
                        provider_id, collection_id, account_json, item_count,
                        refreshed_at, collection_type, active
                    ) VALUES ('yandex_music', 'liked', '{}', 1,
                              datetime('now'), 'liked', 1)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO provider_collection_items(
                        provider_id, collection_id, external_id, position, payload_json
                    ) VALUES ('yandex_music', 'liked', '9', 0, ?)
                    """,
                    (json.dumps(payload),),
                )

            service = LibraryCoverageService(database_path=db)
            before = service.summary()
            self.assertEqual(before["total"], 1)
            self.assertEqual(before["notAnalyzed"], 1)

            # Simulate a refreshed Yandex dataset that marks the collection inactive
            # while an old membership row is still present. Coverage must begin from
            # active snapshots, not from orphan/stale membership rows.
            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    UPDATE provider_collection_snapshots
                    SET active=0
                    WHERE provider_id='yandex_music' AND collection_id='liked'
                    """
                )

            after = service.summary()
            self.assertEqual(after["total"], 0)
            self.assertEqual(service.tracks(status="not_analyzed")["count"], 0)
            with self.assertRaises(ValueError):
                service.set_action("9", "wanted")


if __name__ == "__main__":
    unittest.main()
