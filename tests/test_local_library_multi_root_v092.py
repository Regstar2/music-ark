"""Regression coverage for v0.9.2 Local Library multi-root queries."""

from __future__ import annotations

from contextlib import closing
import sqlite3
from pathlib import Path
import tempfile
import unittest

from musicark.local_library.service import LocalLibraryService
from musicark.mvp_bridge import BridgeRequestError, _parse_root_ids
from musicark.storage.database import initialize_database
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


class LocalLibraryMultiRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.base = Path(self._temp.name)
        self.db_path = self.base / "musicark.db"
        initialize_database(self.db_path)
        self.repository = LocalLibraryStorageRepository(self.db_path)
        self.roots = []
        for name in ("root-one", "root-two", "root-three"):
            directory = self.base / name
            directory.mkdir()
            self.roots.append(self.repository.add_root(directory))

        self._insert_track(self.roots[0].id, "A Song", "Artist A", "Z Album", 100)
        self._insert_track(self.roots[0].id, "D Song", "Shared Artist", "A Album", 140)
        self._insert_track(self.roots[1].id, "B Song", "Shared Artist", "B Album", 110)
        self._insert_track(self.roots[2].id, "C Song", "Artist C", "C Album", 120)

    def _insert_track(
        self,
        root_id: int,
        title: str,
        artist: str,
        album: str,
        duration: int,
    ) -> None:
        path = self.base / f"root-{root_id}" / f"{title}.mp3"
        normalized = str(path).replace("\\", "/").casefold()
        with closing(sqlite3.connect(self.db_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO local_audio_files(
                        library_root_id, path, normalized_path, file_name, extension,
                        sha256, file_size, modified_ns, duration_seconds, codec,
                        metadata_json, title, artists_json, album, availability
                    ) VALUES (?, ?, ?, ?, '.mp3', ?, 1000, 1, ?, 'mp3', '{}', ?, ?, ?, 'available')
                    """,
                    (
                        root_id,
                        str(path),
                        normalized,
                        path.name,
                        f"sha-{root_id}-{title}",
                        duration,
                        title,
                        f'["{artist}"]',
                        album,
                    ),
                )

    def test_none_means_all_roots(self) -> None:
        items, count = self.repository.list_tracks(limit=50, offset=0, root_ids=None)
        self.assertEqual(count, 4)
        self.assertEqual({item["rootId"] for item in items}, {root.id for root in self.roots})

    def test_single_root_list_filters_before_count(self) -> None:
        root_id = self.roots[0].id
        items, count = self.repository.list_tracks(limit=50, offset=0, root_ids=[root_id])
        self.assertEqual(count, 2)
        self.assertEqual({item["rootId"] for item in items}, {root_id})

    def test_multiple_roots_are_unioned(self) -> None:
        wanted = [self.roots[0].id, self.roots[2].id]
        items, count = self.repository.list_tracks(limit=50, offset=0, root_ids=wanted)
        self.assertEqual(count, 3)
        self.assertEqual({item["rootId"] for item in items}, set(wanted))

    def test_empty_root_list_returns_no_tracks(self) -> None:
        items, count = self.repository.list_tracks(limit=50, offset=0, root_ids=[])
        self.assertEqual(count, 0)
        self.assertEqual(items, [])

    def test_search_is_applied_inside_selected_roots(self) -> None:
        items, count = self.repository.list_tracks(
            limit=50,
            offset=0,
            search="Shared Artist",
            root_ids=[self.roots[0].id],
        )
        self.assertEqual(count, 1)
        self.assertEqual([item["title"] for item in items], ["D Song"])

    def test_sort_is_applied_to_filtered_set(self) -> None:
        items, count = self.repository.list_tracks(
            limit=50,
            offset=0,
            sort="album",
            root_ids=[self.roots[0].id, self.roots[2].id],
        )
        self.assertEqual(count, 3)
        self.assertEqual([item["album"] for item in items], ["A Album", "C Album", "Z Album"])

    def test_pagination_count_and_offset_use_selected_roots(self) -> None:
        wanted = [self.roots[0].id, self.roots[2].id]
        first, count = self.repository.list_tracks(
            limit=2,
            offset=0,
            sort="title",
            root_ids=wanted,
        )
        second, count_again = self.repository.list_tracks(
            limit=2,
            offset=2,
            sort="title",
            root_ids=wanted,
        )
        self.assertEqual(count, 3)
        self.assertEqual(count_again, 3)
        self.assertEqual([item["title"] for item in first], ["A Song", "C Song"])
        self.assertEqual([item["title"] for item in second], ["D Song"])

    def test_service_preserves_empty_list_semantics(self) -> None:
        service = LocalLibraryService(database_path=self.db_path)
        payload = service.tracks(root_ids=[])
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["items"], [])

    def test_single_and_multi_root_parameters_are_mutually_exclusive(self) -> None:
        service = LocalLibraryService(database_path=self.db_path)
        with self.assertRaisesRegex(ValueError, "cannot be supplied together"):
            service.tracks(root_id=self.roots[0].id, root_ids=[self.roots[1].id])

    def test_bridge_root_ids_json_is_typed_deduplicated_and_distinguishes_empty(self) -> None:
        self.assertIsNone(_parse_root_ids(None))
        self.assertEqual(_parse_root_ids("[]"), [])
        self.assertEqual(_parse_root_ids("[1,3,1]"), [1, 3])

    def test_bridge_rejects_malformed_root_ids(self) -> None:
        for raw in ("1,2", "{}", '[1,"2"]', "[true]", "[0]", "[-1]"):
            with self.subTest(raw=raw):
                with self.assertRaises(BridgeRequestError):
                    _parse_root_ids(raw)


if __name__ == "__main__":
    unittest.main()
