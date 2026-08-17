"""v0.8.2 follow-up: explicit user acceptance of reviewed recording variants."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.coverage.service import LibraryCoverageService
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.policy import MATCHER_VERSION
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository
from musicark.sync.service import SyncService
from musicark.variant.acceptance import VariantAcceptanceError, VariantAcceptanceService

P = "yandex_music"


class VariantAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        initialize_database(self.db)

    def _variant(self, status: str = "different_version") -> tuple[str, int]:
        external_id = "accepted-variant"
        path = self.root / "accepted.flac"
        path.write_bytes(b"owned-test-audio")
        payload = {
            "provider_id": P,
            "external_id": external_id,
            "title": "Track",
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 180.0,
        }
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                """INSERT INTO provider_collection_snapshots(
                    provider_id,collection_id,account_json,item_count,refreshed_at,
                    collection_type,external_id,title,metadata_json,source_position,active)
                    VALUES(?, 'liked','{}',1,datetime('now'),'liked',NULL,
                           'Мне нравится','{}',0,1)""",
                (P,),
            )
            conn.execute(
                "INSERT INTO provider_collection_items(provider_id,collection_id,external_id,position,payload_json) VALUES(?,'liked',?,0,?)",
                (P, external_id, json.dumps(payload)),
            )
            conn.execute(
                "INSERT INTO provider_tracks(provider_id,external_id,payload_json) VALUES(?,?,?)",
                (P, external_id, json.dumps(payload)),
            )
            cur = conn.execute(
                """INSERT INTO local_audio_files(
                    path,sha256,file_size,duration_seconds,codec,metadata_json,
                    normalized_path,file_name,extension,modified_ns,title,artists_json,
                    album,availability,updated_at)
                    VALUES(?,'sha',?,180,'flac','{}',?,?,'.flac',?,?,'[\"Artist\"]',
                           'Album','available',datetime('now'))""",
                (str(path), path.stat().st_size, str(path).replace('\\','/').casefold(), path.name, path.stat().st_mtime_ns, path.stem),
            )
            local_id = int(cur.lastrowid)
        local_fp = MatchingStorageRepository(self.db).local_library_fingerprint()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                """INSERT INTO matching_results(
                    provider_id,external_id,status,local_file_id,confidence,method,reason,
                    matcher_version,provider_fingerprint,local_fingerprint,manual,updated_at)
                    VALUES(?,?,'matched',?,.99,'automatic','test',?,?,?,0,datetime('now'))""",
                (P, external_id, local_id, MATCHER_VERSION, provider_fingerprint(P, external_id, payload), local_fp),
            )
            conn.execute(
                """INSERT INTO track_links(
                    track_id,source_provider_id,source_external_id,local_file_id,confidence,match_method)
                    VALUES(1,?,?,?,.99,'automatic')""",
                (P, external_id, local_id),
            )
            conn.execute(
                """INSERT INTO track_variant_results(
                    provider_id,external_id,local_file_id,status,
                    provider_variant_fingerprint,local_audio_fingerprint,
                    reference_audio_fingerprint,analyzer_version)
                    VALUES(?,?,?,?,'provider-fp','local-fp','reference-fp',7)""",
                (P, external_id, local_id, status),
            )
        return external_id, local_id

    def test_acceptance_is_separate_from_analyzer_status(self) -> None:
        external_id, local_id = self._variant("different_version")
        service = VariantAcceptanceService(base_dir=self.root, database_path=self.db)
        self.assertFalse(service.get(external_id, local_id)["accepted"])
        accepted = service.accept(external_id, local_id)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["variantStatus"], "different_version")
        with closing(sqlite3.connect(self.db)) as conn:
            raw_status = conn.execute(
                "SELECT status FROM track_variant_results WHERE provider_id=? AND external_id=? AND local_file_id=?",
                (P, external_id, local_id),
            ).fetchone()[0]
        self.assertEqual(raw_status, "different_version")
        self.assertFalse(service.reset(external_id, local_id)["accepted"])

    def test_non_review_variant_cannot_be_accepted(self) -> None:
        external_id, local_id = self._variant("same")
        service = VariantAcceptanceService(base_dir=self.root, database_path=self.db)
        with self.assertRaises(VariantAcceptanceError):
            service.accept(external_id, local_id)

    def test_changed_analysis_invalidates_old_acceptance(self) -> None:
        external_id, local_id = self._variant("altered")
        service = VariantAcceptanceService(base_dir=self.root, database_path=self.db)
        self.assertTrue(service.accept(external_id, local_id)["accepted"])
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                """UPDATE track_variant_results
                   SET local_audio_fingerprint='new-local-fp', updated_at=datetime('now','+1 second')
                   WHERE provider_id=? AND external_id=? AND local_file_id=?""",
                (P, external_id, local_id),
            )
        self.assertFalse(service.get(external_id, local_id)["accepted"])

    def test_accepted_review_variant_no_longer_blocks_coverage_or_sync(self) -> None:
        external_id, local_id = self._variant("different_version")
        coverage = LibraryCoverageService(base_dir=self.root, database_path=self.db)
        self.assertEqual(coverage.track(external_id)["track"]["variantStatus"], "different_version")
        before = SyncService(base_dir=self.root, database_path=self.db).create_plan(scope_type="liked")
        self.assertEqual(before["summary"]["variantIssues"], 1)
        VariantAcceptanceService(base_dir=self.root, database_path=self.db).accept(external_id, local_id)
        self.assertEqual(coverage.track(external_id)["track"]["variantStatus"], "same")
        after = SyncService(base_dir=self.root, database_path=self.db).create_plan(scope_type="liked")
        self.assertEqual(after["summary"]["variantIssues"], 0)
        self.assertFalse(any(item["type"] == "review_variant" for item in after["operations"]))

    def test_schema_migrates_to_1_8_4(self) -> None:
        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
            table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='variant_user_acceptance'").fetchone()
        self.assertEqual(version, "1.8.4")
        self.assertIsNotNone(table)


if __name__ == "__main__":
    unittest.main()
