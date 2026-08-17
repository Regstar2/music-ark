"""v0.8.2 regression tests for explicit local metadata edits."""

from __future__ import annotations

from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from musicark.coverage.service import LibraryCoverageService
from musicark.local_library.service import LocalLibraryService
from musicark.metadata.formats.mp3 import Mp3MetadataAdapter
from musicark.metadata.identity import ExplicitIdentityService
from musicark.metadata.service import MetadataEditorError, MetadataEditorService
from musicark.matching.candidates import CandidateGenerator
from musicark.matching.indexer import LocalMatchIndex
from musicark.matching.scoring import MatchScorer
from musicark.provenance import (
    MUSICARK_EXTERNAL_ID, MUSICARK_METADATA_SCHEMA, MUSICARK_METADATA_SCHEMA_VERSION,
    MUSICARK_PROVIDER, YANDEX_TRACK_ID,
)
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository


def _make_mp3(path: Path, seconds: float = 0.35) -> None:
    """Build real tiny MPEG audio so Mutagen validates the stream, not only the ID3 header."""
    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - dependency is part of MusicArk install.
        raise unittest.SkipTest("imageio-ffmpeg is unavailable") from exc
    wav = path.with_suffix(".wav")
    sample_rate = 44100
    with wave.open(str(wav), "w") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for n in range(int(seconds * sample_rate)):
            sample = int(9000 * math.sin(2 * math.pi * 440.0 * n / sample_rate))
            frames.extend(struct.pack("<h", sample))
        output.writeframes(bytes(frames))
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "6", str(path)],
        check=True,
    )
    wav.unlink()


def _png_1x1() -> bytes:
    # Valid 1x1 transparent PNG.
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"
    )


class Mp3MetadataAdapterTests(unittest.TestCase):
    def test_round_trip_preserves_unknown_txxx_and_supports_rich_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            _make_mp3(path)
            from mutagen.id3 import ID3, TIT2, TPE1, TXXX

            tags = ID3(str(path))
            tags.add(TIT2(encoding=3, text=["Призраков Не Существует"]))
            tags.add(TPE1(encoding=3, text=["drivemusic.me"]))
            tags.add(TXXX(encoding=3, desc="UNKNOWN_VENDOR_TAG", text=["keep-me"]))
            tags.save(str(path), v2_version=4)

            adapter = Mp3MetadataAdapter()
            adapter.apply(
                path,
                {
                    "title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                    "subtitle": "Тест",
                    "version": "Album Version",
                    "artists": ["ЯМАУГЛИ", "Guest"],
                    "album": "Album",
                    "albumArtists": ["ЯМАУГЛИ"],
                    "trackNumber": 5,
                    "totalTracks": 12,
                    "discNumber": 1,
                    "totalDiscs": 2,
                    "releaseDate": "2024-01-02",
                    "genres": ["Alternative", "Rock"],
                    "isrc": "RUA012345678",
                    "publisher": "Publisher",
                    "label": "Label",
                    "copyright": "© 2024",
                    "composer": "Composer",
                    "lyricist": "Lyricist",
                    "bpm": "120",
                    "comment": "Комментарий",
                    "grouping": "Group",
                    "lyrics": "Текст",
                    "explicit": True,
                },
                artwork_data=_png_1x1(),
                artwork_mime="image/png",
            )
            first = adapter.read(path)
            fields = first["fields"]
            self.assertEqual(fields["title"], "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ")
            self.assertEqual(fields["artists"], ["ЯМАУГЛИ", "Guest"])
            self.assertEqual((fields["trackNumber"], fields["totalTracks"]), (5, 12))
            self.assertEqual((fields["discNumber"], fields["totalDiscs"]), (1, 2))
            self.assertEqual(fields["isrc"], "RUA012345678")
            self.assertTrue(fields["explicit"])
            self.assertIsNotNone(adapter.artwork(path))

            # Critical preservation case: editing only Title must not destroy other or
            # unknown/custom frames.
            adapter.apply(path, {"title": "Новое название"})
            after = adapter.read(path)
            self.assertEqual(after["fields"]["artists"], ["ЯМАУГЛИ", "Guest"])
            self.assertEqual(after["fields"]["album"], "Album")
            tags = ID3(str(path))
            unknown = tags.getall("TXXX:UNKNOWN_VENDOR_TAG")
            self.assertEqual([str(value) for value in unknown[0].text], ["keep-me"])

    def test_artwork_add_replace_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "track.mp3"
            _make_mp3(path)
            adapter = Mp3MetadataAdapter()
            adapter.apply(path, {}, artwork_data=_png_1x1(), artwork_mime="image/png")
            self.assertEqual(adapter.artwork(path)[1], "image/png")
            replacement = _png_1x1() + b"ignored-after-iend"
            adapter.apply(path, {}, artwork_data=replacement, artwork_mime="image/png")
            self.assertEqual(adapter.artwork(path)[0], replacement)
            adapter.apply(path, {}, remove_artwork=True)
            self.assertIsNone(adapter.artwork(path))


class MetadataTransactionTests(unittest.TestCase):
    def test_failure_before_atomic_replace_keeps_original_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            path = root / "track.mp3"
            _make_mp3(path)
            adapter = Mp3MetadataAdapter()
            adapter.apply(path, {"title": "Original", "artists": ["Artist"]})

            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            track = local.tracks(limit=10)["items"][0]
            original = path.read_bytes()
            service = MetadataEditorService(base_dir=base)
            with patch("musicark.metadata.service.os.replace", side_effect=OSError("injected replace failure")):
                with self.assertRaises(MetadataEditorError):
                    service.update(int(track["id"]), {"title": "Changed"}, confirm=True)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(adapter.read(path)["fields"]["title"], "Original")


    def test_metadata_only_repair_reindexes_and_rematches_without_exact_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            path = root / "Ямаугли - Призраков Не Существует.mp3"
            _make_mp3(path)
            adapter = Mp3MetadataAdapter()
            adapter.apply(path, {"title": "Призраков Не Существует", "artists": ["drivemusic.me"]})

            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            item = local.tracks(limit=10)["items"][0]
            file_id = int(item["id"])
            db_path = base / ".musicark" / "musicark.db"
            payload = {
                "title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                "artists": ["ЯМАУГЛИ"],
                "album_title": "Album",
                "duration_seconds": float(item["durationSeconds"]),
            }
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        "INSERT INTO provider_tracks(provider_id, external_id, payload_json) VALUES ('yandex_music','123456',?)",
                        (json.dumps(payload, ensure_ascii=False),),
                    )

            # CandidateGenerator is an internal matching primitive. Public Matching
            # refreshes the normalized Local Library index before candidate generation,
            # so this direct unit-level call must reproduce that precondition.
            LocalMatchIndex(db_path).refresh()
            repo = MatchingStorageRepository(db_path)
            provider = repo.list_provider_track_candidates("yandex_music")[0]
            generator = CandidateGenerator(repo, database_path=db_path)
            before_candidate = generator.generate(provider)[0]
            before = MatchScorer().score(provider, before_candidate)
            self.assertNotEqual(before.method.value, "exact_id")

            result = MetadataEditorService(base_dir=base).update(
                file_id,
                {"title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ", "artists": ["ЯМАУГЛИ"], "album": "Album"},
                confirm=True,
            )
            self.assertGreaterEqual(int(result["matching"]["recalculated"]), 1)
            after_fields = adapter.read(path)["fields"]
            self.assertEqual(after_fields["artists"], ["ЯМАУГЛИ"])
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT status, method, confidence, reason FROM matching_results WHERE provider_id='yandex_music' AND external_id='123456'"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "matched")
            self.assertNotEqual(row[1], "exact_id")
            self.assertLessEqual(float(row[2]), 1.0)

    def test_trusted_embedded_identity_recovers_exact_after_fresh_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            path = root / "renamed-anything.mp3"
            _make_mp3(path)
            Mp3MetadataAdapter().apply(
                path,
                {"title": "Any local title", "artists": ["Any artist"]},
                provenance={
                    MUSICARK_PROVIDER: "yandex_music",
                    MUSICARK_EXTERNAL_ID: "777",
                    MUSICARK_METADATA_SCHEMA: MUSICARK_METADATA_SCHEMA_VERSION,
                    YANDEX_TRACK_ID: "777",
                },
            )
            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            db_path = base / ".musicark" / "musicark.db"
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        "INSERT INTO provider_tracks(provider_id, external_id, payload_json) VALUES ('yandex_music','777',?)",
                        (json.dumps({"title": "Different provider title", "artists": ["Provider artist"]}),),
                    )
            repo = MatchingStorageRepository(db_path)
            provider = repo.list_provider_track_candidates("yandex_music")[0]
            candidates = CandidateGenerator(repo, database_path=db_path).generate(provider)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["source_external_id"], "777")
            scored = MatchScorer().score(provider, candidates[0])
            self.assertEqual(scored.method.value, "exact_id")
            self.assertEqual(scored.confidence, 1.0)

    def test_user_confirmed_bind_is_exact_id_one_point_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            path = root / "track.mp3"
            _make_mp3(path)
            Mp3MetadataAdapter().apply(
                path,
                {"title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ", "artists": ["ЯМАУГЛИ"]},
            )
            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            file_id = int(local.tracks(limit=10)["items"][0]["id"])
            db_path = base / ".musicark" / "musicark.db"
            initialize_database(db_path)
            with closing(sqlite3.connect(db_path)) as conn:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO provider_collection_snapshots(
                            provider_id, collection_id, account_json, item_count, refreshed_at,
                            collection_type, title, metadata_json, source_position, active
                        ) VALUES ('yandex_music', 'liked', '{}', 1, datetime('now'),
                                  'liked', 'Мне нравится', '{}', 0, 1)
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO provider_collection_items(
                            provider_id, collection_id, external_id, position, payload_json
                        ) VALUES ('yandex_music', 'liked', '123456', 0, ?)
                        """,
                        (json.dumps({
                            "provider_id": "yandex_music",
                            "external_id": "123456",
                            "title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                            "artists": ["ЯМАУГЛИ"],
                            "album_title": "Album",
                            "duration_seconds": 1.0,
                        }, ensure_ascii=False),),
                    )
            identity = ExplicitIdentityService(db_path)
            result = identity.bind_yandex(
                external_id="123456",
                local_file_id=file_id,
                provider_payload={
                    "title": "ПРИЗРАКОВ НЕ СУЩЕСТВУЕТ",
                    "artists": ["ЯМАУГЛИ"],
                    "album_title": "Album",
                    "duration_seconds": 1.0,
                },
            )
            self.assertEqual(result["method"], "exact_id")
            self.assertEqual(result["confidence"], 1.0)
            self.assertEqual(result["reason"], "user_confirmed")
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT status, method, confidence, reason, manual FROM matching_results WHERE external_id='123456'"
                ).fetchone()
            self.assertEqual(row, ("matched", "exact_id", 1.0, "user_confirmed", 1))
            coverage = LibraryCoverageService(database_path=db_path)
            self.assertEqual(coverage.summary()["covered"], 1)
            self.assertEqual(coverage.summary()["missing"], 0)
            self.assertEqual(coverage.tracks(status="missing")["count"], 0)


class MetadataEditorFollowupTests(unittest.TestCase):
    def test_comment_reader_flattens_values_and_repairs_cp1251_mojibake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comment.mp3"
            _make_mp3(path)
            from mutagen.id3 import COMM, ID3

            expected = "Только для некоммерческого использования"
            broken = expected.encode("cp1251").decode("latin-1")
            tags = ID3(str(path))
            tags.add(COMM(encoding=3, lang="eng", desc="MusicArk", text=[broken]))
            tags.save(str(path), v2_version=4)

            parsed = Mp3MetadataAdapter().read(path)
            self.assertEqual(parsed["fields"]["comment"], expected)
            comment_rows = [row for row in parsed["allTags"] if row["frameId"] == "COMM"]
            self.assertEqual(comment_rows[0]["values"], [expected])
            self.assertNotIn("['", parsed["fields"]["comment"])

    def test_filename_edit_renames_file_and_preserves_local_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            old_path = root / "bad-name.mp3"
            _make_mp3(old_path)
            adapter = Mp3MetadataAdapter()
            adapter.apply(old_path, {"title": "Title", "artists": ["Artist"]})
            before_duration = adapter.validate_audio(old_path)

            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            before = local.tracks(limit=10)["items"][0]
            file_id = int(before["id"])

            result = MetadataEditorService(base_dir=base).update(
                file_id, {"fileName": "Artist - Title.mp3"}, confirm=True
            )
            new_path = root / "Artist - Title.mp3"
            self.assertFalse(old_path.exists())
            self.assertTrue(new_path.exists())
            self.assertTrue(result["fileRename"]["changed"])
            self.assertEqual(result["fileRename"]["fileName"], "Artist - Title.mp3")
            self.assertAlmostEqual(adapter.validate_audio(new_path), before_duration, delta=0.1)

            after = local.track(file_id)["track"]
            self.assertEqual(int(after["id"]), file_id)
            self.assertEqual(after["fileName"], "Artist - Title.mp3")
            self.assertEqual(Path(after["path"]), new_path.resolve())

    def test_filename_collision_is_rejected_before_audio_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "music"
            root.mkdir()
            first = root / "first.mp3"
            second = root / "second.mp3"
            _make_mp3(first)
            _make_mp3(second)
            Mp3MetadataAdapter().apply(first, {"title": "First", "artists": ["Artist"]})
            Mp3MetadataAdapter().apply(second, {"title": "Second", "artists": ["Artist"]})
            original = first.read_bytes()

            local = LocalLibraryService(base_dir=base)
            local.add_root(root)
            local.scan()
            first_id = next(
                int(item["id"])
                for item in local.tracks(limit=10)["items"]
                if item["fileName"] == "first.mp3"
            )
            with self.assertRaises(MetadataEditorError):
                MetadataEditorService(base_dir=base).update(
                    first_id, {"fileName": "second.mp3"}, confirm=True
                )
            self.assertEqual(first.read_bytes(), original)
            self.assertTrue(second.exists())

    def test_yandex_filename_suggestion_uses_artist_dash_title(self) -> None:
        from musicark.download.metadata import YandexTrackMetadata

        metadata = YandexTrackMetadata(
            provider_id="yandex_music",
            external_id="42",
            title="Название",
            artists=("Автор",),
        )
        self.assertEqual(
            MetadataEditorService._suggested_filename(metadata, ".mp3"),
            "Автор - Название.mp3",
        )


if __name__ == "__main__":
    unittest.main()
