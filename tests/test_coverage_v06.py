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


PROVIDER = "yandex_music"


class CoverageV06Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        initialize_database(self.db)

    def _snapshot(
        self,
        collection_id: str,
        *,
        title: str,
        collection_type: str,
        external_id: str | None = None,
        position: int = 0,
    ) -> None:
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO provider_collection_snapshots(
                        provider_id, collection_id, account_json, item_count,
                        refreshed_at, collection_type, external_id, title,
                        metadata_json, source_position, active
                    ) VALUES (?, ?, '{}', 0, datetime('now'), ?, ?, ?, '{}', ?, 1)
                    """,
                    (
                        PROVIDER,
                        collection_id,
                        collection_type,
                        external_id,
                        title,
                        position,
                    ),
                )

    @staticmethod
    def _payload(
        external_id: str,
        title: str,
        *,
        artist: str = "Artist",
        album: str = "Album",
        duration: float = 180.0,
    ) -> dict[str, object]:
        return {
            "provider_id": PROVIDER,
            "external_id": external_id,
            "title": title,
            "artists": [artist],
            "album_title": album,
            "duration_seconds": duration,
        }

    def _member(
        self,
        collection_id: str,
        external_id: str,
        *,
        title: str,
        position: int,
        storage_external_id: str | None = None,
    ) -> dict[str, object]:
        payload = self._payload(external_id, title)
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO provider_collection_items(
                        provider_id, collection_id, external_id, position, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        PROVIDER,
                        collection_id,
                        storage_external_id or external_id,
                        position,
                        json.dumps(payload),
                    ),
                )
                conn.execute(
                    """
                    UPDATE provider_collection_snapshots
                    SET item_count=item_count+1
                    WHERE provider_id=? AND collection_id=?
                    """,
                    (PROVIDER, collection_id),
                )
        return payload

    def _local(self, name: str = "local.flac") -> int:
        path = self.root / name
        path.write_bytes(b"owned-test-audio")
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO local_audio_files(
                        path, sha256, file_size, duration_seconds, codec, metadata_json,
                        modified_ns, title, artists_json, album, availability, updated_at
                    ) VALUES (?, 'sha', ?, 180, 'flac', '{}', ?, 'Song', '["Artist"]',
                              'Album', 'available', datetime('now'))
                    """,
                    (str(path), path.stat().st_size, path.stat().st_mtime_ns),
                )
                return int(cursor.lastrowid)

    def _automatic_result(
        self,
        external_id: str,
        payload: dict[str, object],
        status: str,
        *,
        local_file_id: int | None = None,
        reason: str = "test",
    ) -> None:
        local_fp = MatchingStorageRepository(self.db).local_library_fingerprint()
        provider_fp = provider_fingerprint(PROVIDER, external_id, payload)
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO matching_results(
                        provider_id, external_id, status, local_file_id, confidence,
                        method, reason, matcher_version, provider_fingerprint,
                        local_fingerprint, manual
                    ) VALUES (?, ?, ?, ?, ?, 'automatic', ?, ?, ?, ?, 0)
                    """,
                    (
                        PROVIDER,
                        external_id,
                        status,
                        local_file_id,
                        0.98 if status == "matched" else 0.0,
                        reason,
                        MATCHER_VERSION,
                        provider_fp,
                        local_fp,
                    ),
                )
                if status == "matched" and local_file_id is not None:
                    conn.execute(
                        """
                        INSERT INTO track_links(
                            track_id, source_provider_id, source_external_id,
                            local_file_id, confidence, match_method
                        ) VALUES (1, ?, ?, ?, 0.98, 'automatic')
                        """,
                        (PROVIDER, external_id, local_file_id),
                    )

    def _service(self) -> LibraryCoverageService:
        return LibraryCoverageService(database_path=self.db)

    def test_truth_table_and_not_analyzed(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        matched = self._member("liked", "1", title="Matched", position=0)
        missing = self._member("liked", "2", title="Missing", position=1)
        conflict = self._member("liked", "3", title="Conflict", position=2)
        self._member("liked", "4", title="Unknown", position=3)
        local_id = self._local()

        self._automatic_result("1", matched, "matched", local_file_id=local_id)
        self._automatic_result("2", missing, "unmatched")
        self._automatic_result("3", conflict, "conflict")

        summary = self._service().summary()
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["covered"], 1)
        self.assertEqual(summary["missing"], 1)
        self.assertEqual(summary["needsReview"], 1)
        self.assertEqual(summary["notAnalyzed"], 1)

    def test_every_variant_status_remains_identity_covered(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        statuses = ["same", "altered", "different_version", "uncertain", "not_checked"]
        payloads = []
        local_ids = []
        for i, status in enumerate(statuses, start=1):
            payload = self._member("liked", str(i), title=f"Track {i}", position=i)
            local_ids.append(self._local(f"{i}.flac"))
            payloads.append((str(i), payload, status))

        for (external_id, payload, _status), local_id in zip(payloads, local_ids):
            self._automatic_result(
                external_id, payload, "matched", local_file_id=local_id
            )

        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                for (external_id, _payload, status), local_id in zip(payloads, local_ids):
                    conn.execute(
                        """
                        INSERT INTO track_variant_results(
                            provider_id, external_id, local_file_id, status
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (PROVIDER, external_id, local_id, status),
                    )

        summary = self._service().summary()
        self.assertEqual(summary["covered"], 5)
        self.assertEqual(summary["missing"], 0)
        self.assertEqual(
            summary["variantVerification"],
            {
                "same": 1,
                "altered": 1,
                "differentVersion": 1,
                "uncertain": 1,
                "notChecked": 1,
            },
        )

    def test_reference_cache_never_counts_as_local_coverage(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        payload = self._member("liked", "203", title="Reference Only", position=0)
        self._automatic_result("203", payload, "unmatched")

        reference = self.root / ".musicark" / "downloads" / "yandex" / "yandex_203.mp3"
        reference.parent.mkdir(parents=True)
        reference.write_bytes(b"reference-only")

        result = self._service().tracks(status="missing")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["externalId"], "203")
        self.assertEqual(result["items"][0]["coverageStatus"], "missing")

    def test_global_identity_is_unique_across_collections_and_duplicate_occurrences(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        self._snapshot(
            "playlist:workout", title="Workout", collection_type="playlist", external_id="workout"
        )
        payload = self._member("liked", "42", title="Once", position=0)
        self._member("playlist:workout", "42", title="Once", position=5)
        self._member(
            "playlist:workout", "42", title="Once", position=6, storage_external_id="42::duplicate:1"
        )
        self._automatic_result("42", payload, "unmatched")

        service = self._service()
        self.assertEqual(service.summary()["total"], 1)
        item = service.tracks(status="missing")["items"][0]
        self.assertEqual(
            {entry["id"] for entry in item["collections"]}, {"liked", "playlist:workout"}
        )

    def test_collection_scopes_and_playlist_order(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        self._snapshot("playlist:a", title="A", collection_type="playlist", external_id="a")
        p1 = self._member("liked", "1", title="Liked only", position=0)
        p2 = self._member("playlist:a", "2", title="Second", position=1)
        p3 = self._member("playlist:a", "3", title="First", position=0)
        for external_id, payload in (("1", p1), ("2", p2), ("3", p3)):
            self._automatic_result(external_id, payload, "unmatched")

        service = self._service()
        self.assertEqual(service.summary()["total"], 3)
        self.assertEqual(service.summary(collection_id="liked")["total"], 1)
        self.assertEqual(service.summary(collection_id="playlist:a")["total"], 2)
        page = service.tracks(collection_id="playlist:a", status="missing", sort="position")
        self.assertEqual([item["externalId"] for item in page["items"]], ["3", "2"])

    def test_removed_provider_track_disappears_from_active_coverage(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        payload = self._member("liked", "9", title="Gone", position=0)
        self._automatic_result("9", payload, "unmatched")
        self.assertEqual(self._service().summary()["total"], 1)

        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    "DELETE FROM provider_collection_items WHERE provider_id=? AND collection_id='liked'",
                    (PROVIDER,),
                )
        self.assertEqual(self._service().summary()["total"], 0)

    def test_user_actions_persist_and_reset(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        payload = self._member("liked", "77", title="Wanted", position=0)
        self._automatic_result("77", payload, "unmatched")

        self._service().set_action("77", "wanted")
        restarted = self._service()
        wanted = restarted.tracks(status="missing", user_action="wanted")
        self.assertEqual(wanted["count"], 1)

        restarted.set_action("77", "ignored")
        ignored = self._service().tracks(status="missing", user_action="ignored")
        self.assertEqual(ignored["count"], 1)

        self._service().set_action("77", "unreviewed")
        unreviewed = self._service().tracks(status="missing", user_action="unreviewed")
        self.assertEqual(unreviewed["count"], 1)

    def test_stale_automatic_unmatched_becomes_not_analyzed_after_local_change(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        payload = self._member("liked", "88", title="Needs recheck", position=0)
        self._automatic_result("88", payload, "unmatched")
        self.assertEqual(self._service().summary()["missing"], 1)

        self._local("new-file.flac")
        summary = self._service().summary()
        self.assertEqual(summary["missing"], 0)
        self.assertEqual(summary["notAnalyzed"], 1)

    def test_manual_stale_match_is_needs_review_not_covered_or_missing(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        self._member("liked", "99", title="Manual", position=0)
        local_id = self._local()
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO matching_results(
                        provider_id, external_id, status, local_file_id, confidence,
                        method, reason, matcher_version, provider_fingerprint,
                        local_fingerprint, manual
                    ) VALUES (?, '99', 'matched', ?, 1.0, 'manual',
                              'manual_match_stale:local_metadata', ?, '', '', 1)
                    """,
                    (PROVIDER, local_id, MATCHER_VERSION),
                )
                conn.execute(
                    """
                    INSERT INTO track_links(
                        track_id, source_provider_id, source_external_id, local_file_id,
                        confidence, match_method
                    ) VALUES (1, ?, '99', ?, 1.0, 'manual')
                    """,
                    (PROVIDER, local_id),
                )

        summary = self._service().summary()
        self.assertEqual(summary["needsReview"], 1)
        self.assertEqual(summary["covered"], 0)
        self.assertEqual(summary["missing"], 0)

    def test_wanted_decision_is_historical_after_track_becomes_covered(self) -> None:
        self._snapshot("liked", title="Мне нравится", collection_type="liked")
        payload = self._member("liked", "100", title="Later matched", position=0)
        self._automatic_result("100", payload, "unmatched")
        service = self._service()
        service.set_action("100", "wanted")
        self.assertEqual(service.tracks(status="missing", user_action="wanted")["count"], 1)

        local_id = self._local()
        local_fp = MatchingStorageRepository(self.db).local_library_fingerprint()
        provider_fp = provider_fingerprint(PROVIDER, "100", payload)
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE matching_results
                    SET status='matched', local_file_id=?, confidence=.98,
                        provider_fingerprint=?, local_fingerprint=?,
                        matcher_version=?, reason='auto_threshold_and_margin'
                    WHERE provider_id=? AND external_id='100'
                    """,
                    (local_id, provider_fp, local_fp, MATCHER_VERSION, PROVIDER),
                )
                conn.execute(
                    """
                    INSERT INTO track_links(
                        track_id, source_provider_id, source_external_id, local_file_id,
                        confidence, match_method
                    ) VALUES (1, ?, '100', ?, .98, 'automatic')
                    """,
                    (PROVIDER, local_id),
                )

        self.assertEqual(
            self._service().tracks(status="missing", user_action="wanted")["count"], 0
        )
        covered = self._service().tracks(status="covered")
        self.assertEqual(covered["count"], 1)
        self.assertEqual(covered["items"][0]["userAction"], "wanted")

    def test_search_includes_collection_title_and_bulk_action(self) -> None:
        self._snapshot(
            "playlist:favorites", title="Favorites 2026", collection_type="playlist", external_id="favorites"
        )
        p1 = self._member("playlist:favorites", "501", title="Alpha", position=0)
        p2 = self._member("playlist:favorites", "502", title="Beta", position=1)
        self._automatic_result("501", p1, "unmatched")
        self._automatic_result("502", p2, "unmatched")

        service = self._service()
        result = service.tracks(status="missing", search="Favorites 2026")
        self.assertEqual(result["count"], 2)
        service.set_actions(["501", "502"], "wanted")
        self.assertEqual(service.tracks(status="missing", user_action="wanted")["count"], 2)


if __name__ == "__main__":
    unittest.main()
