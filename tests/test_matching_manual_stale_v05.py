"""Manual matches survive reruns but become stale when material metadata changes."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.matching.service import MatchingService
from musicark.providers.models import ProviderTrack
from musicark.storage.database import initialize_database
from musicark.storage.provider_storage import ProviderStorageRepository


class MatchingManualStaleV05Tests(unittest.TestCase):
    def test_manual_match_is_preserved_and_marked_stale_after_local_metadata_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            ProviderStorageRepository(db).upsert_provider_track(
                ProviderTrack(
                    provider_id="yandex_music",
                    external_id="101",
                    title="Song",
                    artists=("Artist",),
                    album_title="Album",
                    duration_seconds=200,
                )
            )
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO local_audio_files(
                            id, path, normalized_path, file_name, extension, sha256,
                            file_size, modified_ns, duration_seconds, codec,
                            metadata_json, title, artists_json, album, availability
                        ) VALUES (
                            1, '/music/Song.flac', '/music/song.flac', 'Song.flac', '.flac',
                            '', 1000, 1, 200, 'flac', ?, 'Song', ?, 'Album', 'available'
                        )
                        """,
                        (
                            json.dumps({"title": "Song", "artists": ["Artist"]}),
                            json.dumps(["Artist"]),
                        ),
                    )

            service = MatchingService(database_path=db)
            service.run()
            service.accept("101", 1)
            accepted = service.result("101")["result"]
            self.assertEqual(accepted["method"], "manual")
            self.assertFalse(accepted["stale"])

            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.execute(
                        """
                        UPDATE local_audio_files
                        SET title='Song (retagged)', modified_ns=2,
                            metadata_json='{"title":"Song (retagged)","artists":["Artist"]}',
                            updated_at=datetime('now')
                        WHERE id=1
                        """
                    )

            rerun = service.run()
            stale = service.result("101")["result"]
            self.assertEqual(rerun["manualStale"], 1)
            self.assertEqual(stale["status"], "matched")
            self.assertEqual(stale["method"], "manual")
            self.assertTrue(stale["stale"])
            self.assertTrue(str(stale["reason"]).startswith("manual_match_stale:"))

            with closing(sqlite3.connect(db)) as conn:
                link = conn.execute(
                    """
                    SELECT local_file_id, match_method FROM track_links
                    WHERE source_provider_id='yandex_music' AND source_external_id='101'
                    """
                ).fetchone()
            self.assertEqual(link, (1, "manual"))

            # Explicit confirmation refreshes the reference and clears stale state.
            service.accept("101", 1)
            confirmed = service.result("101")["result"]
            self.assertFalse(confirmed["stale"])
            self.assertEqual(confirmed["reason"], "manual_accept")


if __name__ == "__main__":
    unittest.main()
