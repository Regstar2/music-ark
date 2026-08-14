"""Provider identity de-duplication tests for v0.5 matching."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.matching.input import MatchingInputRepository
from musicark.matching.service import MatchingService
from musicark.storage.database import initialize_database


class MatchingIdentityV05Tests(unittest.TestCase):
    def test_liked_and_multiple_playlists_materialize_one_provider_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            payload = json.dumps(
                {
                    "provider_id": "yandex_music",
                    "external_id": "123",
                    "title": "One Song",
                    "artists": ["One Artist"],
                    "album_title": "Album",
                    "duration_seconds": 200,
                },
                ensure_ascii=False,
            )
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    for collection_id, position in (("liked", 0), ("playlist:a", 1), ("playlist:b", 2)):
                        conn.execute(
                            """
                            INSERT INTO provider_collection_items(
                                provider_id, collection_id, external_id, position, payload_json
                            ) VALUES ('yandex_music', ?, '123', ?, ?)
                            """,
                            (collection_id, position, payload),
                        )

            count = MatchingInputRepository(db).sync_provider_tracks("yandex_music")
            self.assertEqual(count, 1)
            with closing(sqlite3.connect(db)) as conn:
                provider_rows = conn.execute(
                    "SELECT COUNT(*) FROM provider_tracks WHERE provider_id='yandex_music' AND external_id='123'"
                ).fetchone()[0]
            self.assertEqual(provider_rows, 1)

            result = MatchingService(database_path=db).run()
            self.assertEqual(result["providerIdentities"], 1)
            self.assertEqual(result["total"], 1)


if __name__ == "__main__":
    unittest.main()
