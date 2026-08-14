"""v0.5 matching policy, scoring, ambiguity, scale and persistence tests."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.matching.models import MatchStatus
from musicark.matching.normalize import normalize_artists, normalize_text, title_version_markers
from musicark.matching.scoring import MatchScorer
from musicark.matching.service import MatchingService
from musicark.providers.models import ProviderTrack
from musicark.storage.database import initialize_database
from musicark.storage.provider_storage import ProviderStorageRepository


class MatchingV05Tests(unittest.TestCase):
    def test_normalization_is_deterministic_and_preserves_version_words(self) -> None:
        self.assertEqual(normalize_text(" LINKIN   PARK "), "linkin park")
        self.assertEqual(normalize_text("Linkin—Park"), "linkin park")
        self.assertEqual(normalize_text("Café"), "café")
        self.assertEqual(
            normalize_artists(("Artist A feat. Artist B",)),
            ("artist a", "artist b"),
        )
        self.assertEqual(
            normalize_artists(("Artist B", "Artist A")),
            ("artist a", "artist b"),
        )
        self.assertIn("remix", title_version_markers("Song (Remix)"))
        self.assertIn("live", title_version_markers("Song — Live"))
        self.assertIn("acoustic", title_version_markers("Song Acoustic"))
        self.assertNotEqual(normalize_text("Song"), normalize_text("Song Remix"))

    def test_scoring_prefers_structured_exact_metadata(self) -> None:
        scorer = MatchScorer()
        provider = _provider("1", "Numb", ["Linkin Park"], "Meteora", 185)
        exact = scorer.score(
            provider,
            _local(1, "Numb", ["Linkin Park"], "Meteora", 185.4, "/music/Numb.flac"),
        )
        album_mismatch = scorer.score(
            provider,
            _local(2, "Numb", ["Linkin Park"], "Compilation", 185.4, "/music/Numb.mp3"),
        )
        wrong_artist = scorer.score(
            provider,
            _local(3, "Numb", ["Another Artist"], "Meteora", 185.4, "/music/Numb.ogg"),
        )
        wrong_title = scorer.score(
            provider,
            _local(4, "In the End", ["Linkin Park"], "Meteora", 185.4, "/music/Other.flac"),
        )
        far_duration = scorer.score(
            provider,
            _local(5, "Numb", ["Linkin Park"], "Meteora", 250, "/music/Numb.wav"),
        )
        self.assertGreaterEqual(exact.confidence, 0.95)
        self.assertGreater(album_mismatch.confidence, 0.90)
        self.assertLess(wrong_artist.confidence, 0.70)
        self.assertLess(wrong_title.confidence, 0.70)
        self.assertGreater(exact.confidence, far_duration.confidence)

    def test_live_remix_and_instrumental_are_not_auto_collapsed(self) -> None:
        scorer = MatchScorer()
        provider = _provider("1", "Song", ["Artist"], "Album", 200)
        for local_title in ("Song Live", "Song Remix", "Song Instrumental", "Song Acoustic"):
            scored = scorer.score(
                provider,
                _local(1, local_title, ["Artist"], "Album", 200, f"/music/{local_title}.flac"),
            )
            self.assertLess(scored.confidence, 0.90, local_title)

    def test_exact_yandex_id_convention_is_strict(self) -> None:
        scorer = MatchScorer()
        provider = _provider("69046542", "Ахегао", ["Мэйби Бэйби"], None, 160)
        exact = scorer.score(
            provider,
            _local(1, "Other", [], None, 160, "/music/yandex_69046542.mp3"),
        )
        incidental = scorer.score(
            provider,
            _local(2, "Other", [], None, 160, "/music/album_69046542_track.mp3"),
        )
        self.assertEqual(exact.method.value, "exact_id")
        self.assertGreater(exact.confidence, 0.99)
        self.assertNotEqual(incidental.method.value, "exact_id")

    def test_ambiguity_margin_creates_conflict(self) -> None:
        provider = _provider("1", "Song", ["Artist"], "Album", 200)
        scorer = MatchScorer()
        first = scorer.score(provider, _local(1, "Song", ["Artist"], "Album", 200, "/music/a.flac"))
        second = scorer.score(provider, _local(2, "Song", ["Artist"], "Album", 200.5, "/music/b.mp3"))
        decision = MatchingService._decide(
            provider,
            provider_fingerprint="p",
            local_fingerprint="l",
            candidates=sorted([first, second], key=lambda item: item.confidence, reverse=True),
        )
        self.assertEqual(decision.status, MatchStatus.CONFLICT)
        self.assertEqual(decision.reason, "ambiguous_top_candidates")

    def test_run_persists_auto_conflict_unmatched_and_manual_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            providers = ProviderStorageRepository(db)
            providers.upsert_provider_track(
                ProviderTrack("yandex_music", "1", "Exact", ("Artist",), album_title="Album", duration_seconds=200)
            )
            providers.upsert_provider_track(
                ProviderTrack("yandex_music", "2", "Ambiguous", ("Artist",), album_title="Album", duration_seconds=180)
            )
            providers.upsert_provider_track(
                ProviderTrack("yandex_music", "3", "Missing", ("Nobody",), album_title="Nowhere", duration_seconds=150)
            )
            _insert_local(db, 1, "Exact", ["Artist"], "Album", 200.2, "/music/exact.flac")
            _insert_local(db, 2, "Ambiguous", ["Artist"], "Album", 180.0, "/music/a.flac")
            _insert_local(db, 3, "Ambiguous", ["Artist"], "Album", 180.5, "/music/a.mp3")

            service = MatchingService(database_path=db)
            result = service.run()
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["matched"], 1)
            self.assertEqual(result["conflicts"], 1)
            self.assertEqual(result["unmatched"], 1)
            self.assertLess(result["comparisons"], 3 * 3)

            detail = service.result("2")["result"]
            self.assertGreaterEqual(len(detail["candidates"]), 2)
            service.accept("2", int(detail["candidates"][0]["localFileId"]))
            rerun = service.run()
            self.assertGreaterEqual(rerun["unchanged"], 1)
            accepted = service.result("2")["result"]
            self.assertEqual(accepted["status"], "matched")
            self.assertEqual(accepted["method"], "manual")
            self.assertTrue(accepted["manual"])

            # Create another ambiguous identity and reject its best candidate.
            providers.upsert_provider_track(
                ProviderTrack("yandex_music", "4", "Reject Me", ("Artist",), album_title="Album", duration_seconds=210)
            )
            _insert_local(db, 4, "Reject Me", ["Artist"], "Album", 210.0, "/music/reject.flac")
            _insert_local(db, 5, "Reject Me", ["Artist"], "Album", 210.5, "/music/reject.mp3")
            service.run()
            reject_detail = service.result("4")["result"]
            rejected_id = int(reject_detail["candidates"][0]["localFileId"])
            service.reject("4", rejected_id)
            service.run()
            after_reject = service.result("4")["result"]
            self.assertNotEqual(after_reject.get("localFileId"), rejected_id)

    def test_deleted_local_file_invalidates_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            providers = ProviderStorageRepository(db)
            providers.upsert_provider_track(
                ProviderTrack("yandex_music", "1", "Exact", ("Artist",), duration_seconds=200)
            )
            _insert_local(db, 1, "Exact", ["Artist"], None, 200, "/music/exact.flac")
            service = MatchingService(database_path=db)
            service.run()
            self.assertEqual(service.result("1")["result"]["status"], "matched")
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.execute("DELETE FROM local_audio_files WHERE id=1")
            service.run()
            self.assertEqual(service.result("1")["result"]["status"], "unmatched")

    def test_scale_regression_does_not_score_cartesian_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "musicark.db"
            initialize_database(db)
            with closing(sqlite3.connect(db)) as conn:
                with conn:
                    conn.executemany(
                        "INSERT INTO provider_tracks(provider_id, external_id, payload_json) VALUES ('yandex_music', ?, ?)",
                        [
                            (
                                str(i),
                                json.dumps({
                                    "provider_id": "yandex_music",
                                    "external_id": str(i),
                                    "title": f"Song {i}",
                                    "artists": [f"Artist {i % 20}"],
                                    "album_title": "Album",
                                    "duration_seconds": 180 + (i % 30),
                                }),
                            )
                            for i in range(200)
                        ],
                    )
                    conn.executemany(
                        """
                        INSERT INTO local_audio_files(
                            id, path, normalized_path, file_name, extension, sha256, file_size,
                            duration_seconds, codec, metadata_json, title, artists_json,
                            album, availability
                        ) VALUES (?, ?, ?, ?, '.flac', '', 1000, ?, 'flac', ?, ?, ?, 'Album', 'available')
                        """,
                        [
                            (
                                i + 1,
                                f"/music/song-{i}.flac",
                                f"/music/song-{i}.flac",
                                f"song-{i}.flac",
                                180 + (i % 30),
                                json.dumps({"title": f"Song {i}", "artists": [f"Artist {i % 20}"]}),
                                f"Song {i}",
                                json.dumps([f"Artist {i % 20}"]),
                            )
                            for i in range(2000)
                        ],
                    )
            result = MatchingService(database_path=db).run()
            cartesian = 200 * 2000
            self.assertLessEqual(result["comparisons"], 200 * 40)
            self.assertLess(result["comparisons"], cartesian // 10)


def _provider(
    external_id: str,
    title: str,
    artists: list[str],
    album: str | None,
    duration: int | None,
) -> dict:
    return {
        "provider_id": "yandex_music",
        "external_id": external_id,
        "payload": {
            "provider_id": "yandex_music",
            "external_id": external_id,
            "title": title,
            "artists": artists,
            "album_title": album,
            "duration_seconds": duration,
        },
    }


def _local(
    file_id: int,
    title: str,
    artists: list[str],
    album: str | None,
    duration: float | None,
    path: str,
) -> dict:
    return {
        "id": file_id,
        "path": path,
        "title": title,
        "artists": artists,
        "album": album,
        "duration_seconds": duration,
        "metadata_json": {"title": title, "artists": artists},
        "tag_title_present": True,
    }


def _insert_local(
    db: Path,
    file_id: int,
    title: str,
    artists: list[str],
    album: str | None,
    duration: float | None,
    path: str,
) -> None:
    with closing(sqlite3.connect(db)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO local_audio_files(
                    id, path, normalized_path, file_name, extension, sha256, file_size,
                    duration_seconds, codec, metadata_json, title, artists_json, album,
                    availability
                ) VALUES (?, ?, ?, ?, ?, '', 1000, ?, 'flac', ?, ?, ?, ?, 'available')
                """,
                (
                    file_id,
                    path,
                    path.casefold(),
                    Path(path).name,
                    Path(path).suffix,
                    duration,
                    json.dumps({"title": title, "artists": artists}, ensure_ascii=False),
                    title,
                    json.dumps(artists, ensure_ascii=False),
                    album,
                ),
            )


if __name__ == "__main__":
    unittest.main()
