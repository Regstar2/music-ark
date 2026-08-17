"""v0.8.2 app-level ORIGINAL/CENSORED label persistence."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.content_labels.service import ContentLabelError, ContentLabelService
from musicark.storage.database import initialize_database


class ContentLabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.db = self.base / ".musicark" / "musicark.db"
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO local_audio_files(path, sha256, file_size, codec, availability)
                    VALUES (?, 'sha', 1, 'mp3', 'available')
                    """,
                    (str(self.base / "track.mp3"),),
                )
                self.local_id = int(cursor.lastrowid)
        self.service = ContentLabelService(database_path=self.db)

    def test_schema_is_forward_migrated_to_1_8_3(self) -> None:
        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute(
                "SELECT value FROM app_metadata WHERE key='schema_version'"
            ).fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        self.assertEqual(version, "1.8.3")
        self.assertIn("local_track_content_labels", tables)
        self.assertIn("provider_track_content_labels", tables)

    def test_local_label_can_be_set_changed_and_cleared(self) -> None:
        self.service.set_local(self.local_id, "original")
        self.assertEqual(
            self.service.batch(local_file_ids=[self.local_id])["local"],
            {str(self.local_id): "original"},
        )
        self.service.set_local(self.local_id, "censored")
        self.assertEqual(
            self.service.batch(local_file_ids=[self.local_id])["local"],
            {str(self.local_id): "censored"},
        )
        self.service.set_local(self.local_id, "")
        self.assertEqual(self.service.batch(local_file_ids=[self.local_id])["local"], {})

    def test_yandex_label_is_keyed_by_provider_identity(self) -> None:
        self.service.set_provider("123456", "original")
        self.service.set_provider("777", "censored")
        payload = self.service.batch(external_ids=["123456", "777", "999"])
        self.assertEqual(
            payload["provider"],
            {"123456": "original", "777": "censored"},
        )
        self.service.set_provider("123456", "")
        self.assertEqual(
            self.service.batch(external_ids=["123456", "777"])["provider"],
            {"777": "censored"},
        )

    def test_invalid_label_and_missing_local_file_are_rejected(self) -> None:
        with self.assertRaises(ContentLabelError):
            self.service.set_provider("123", "remix")
        with self.assertRaises(ContentLabelError):
            self.service.set_local(999999, "original")


if __name__ == "__main__":
    unittest.main()
