from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.download.provider import YandexMusicDownloadProvider
from musicark.storage.database import initialize_database
from musicark.variant.models import AudioComparison, ReferenceAudio
from musicark.variant.reference import ReferenceAcquisitionError
from musicark.variant.service import VariantDetectionService


class _MissingResolver:
    def resolve(self, provider_id: str, external_id: str):  # type: ignore[no-untyped-def]
        return None


class _ExistingResolver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def resolve(self, provider_id: str, external_id: str) -> ReferenceAudio:
        return ReferenceAudio(self.path, provider_id, external_id)


class _FakeAcquirer:
    def __init__(self, path: Path | None = None, error: Exception | None = None) -> None:
        self.path = path
        self.error = error
        self.calls = 0

    def acquire(self, provider_id: str, external_id: str) -> ReferenceAudio:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.path is not None
        return ReferenceAudio(self.path, provider_id, external_id)


class _CountingVerifier:
    available = True

    def __init__(self, similarity: float = 0.99) -> None:
        self.similarity = similarity
        self.calls = 0

    def compare(self, reference_path: Path, local_path: Path) -> AudioComparison:
        self.calls += 1
        return AudioComparison(
            alignment_offset_seconds=0.0,
            alignment_confidence=1.0,
            global_similarity=self.similarity,
            median_window_similarity=self.similarity,
            low_similarity_window_ratio=0.0 if self.similarity > 0.9 else 0.8,
            altered_regions=(),
            window_count=20,
        )


class _FakeDownloadInfo:
    codec = "mp3"
    bitrate_in_kbps = 320

    def get_direct_link(self) -> str:
        return "https://example.invalid/reference.mp3"


class _FakeTrack:
    def get_download_info(self):  # type: ignore[no-untyped-def]
        return [_FakeDownloadInfo()]


class _FakeClient:
    def tracks(self, ids):  # type: ignore[no-untyped-def]
        return [_FakeTrack()]


class VariantReferenceAcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        initialize_database(self.db)
        self.local = self.root / "different-local.mp3"
        self.local.write_bytes(b"local-audio-placeholder")
        self.reference = self.root / "yandex_12345.mp3"
        self.reference.write_bytes(b"reference-audio-placeholder")
        self._seed_pair()

    def _seed_pair(self) -> None:
        stat = self.local.stat()
        provider = {
            "provider_id": "yandex_music",
            "external_id": "12345",
            "title": "Song",
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 146.0,
            "explicit": False,
        }
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO provider_tracks(provider_id, external_id, payload_json) VALUES (?, ?, ?)",
                    ("yandex_music", "12345", json.dumps(provider)),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO local_audio_files(
                        path, sha256, file_size, duration_seconds, codec, metadata_json,
                        modified_ns, title, artists_json, album, availability,
                        normalized_path, file_name, extension
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(self.local),
                        "hash",
                        stat.st_size,
                        146.0,
                        "mp3",
                        json.dumps({"title": "Song", "artist": "Artist"}),
                        stat.st_mtime_ns,
                        "Song",
                        '["Artist"]',
                        "Album",
                        "available",
                        str(self.local).casefold(),
                        self.local.name,
                        ".mp3",
                    ),
                )
                local_id = int(cursor.lastrowid)
                conn.execute(
                    """
                    INSERT INTO matching_results(
                        provider_id, external_id, status, local_file_id, confidence,
                        method, score_breakdown_json, reason, matcher_version,
                        provider_fingerprint, local_fingerprint, manual
                    ) VALUES (?, ?, 'matched', ?, 1.0, 'manual', '{}', 'manual_accept', 1, 'p', 'l', 1)
                    """,
                    ("yandex_music", "12345", local_id),
                )

    def test_missing_reference_is_acquired_before_audio_comparison(self) -> None:
        verifier = _CountingVerifier()
        acquirer = _FakeAcquirer(self.reference)
        service = VariantDetectionService(
            database_path=self.db,
            audio_verifier=verifier,  # type: ignore[arg-type]
            reference_resolver=_MissingResolver(),  # type: ignore[arg-type]
            reference_acquirer=acquirer,  # type: ignore[arg-type]
        )

        payload = service.run("12345")
        result = payload["result"]

        self.assertEqual(1, acquirer.calls)
        self.assertEqual(1, verifier.calls)
        self.assertEqual("same", result["variantStatus"])
        self.assertEqual(str(self.reference), result["referencePath"])
        self.assertNotIn("reference_audio_missing", result["variantReasons"])

    def test_reference_acquisition_failure_stays_not_checked(self) -> None:
        verifier = _CountingVerifier()
        acquirer = _FakeAcquirer(
            error=ReferenceAcquisitionError("reference_download_failed: synthetic network failure")
        )
        service = VariantDetectionService(
            database_path=self.db,
            audio_verifier=verifier,  # type: ignore[arg-type]
            reference_resolver=_MissingResolver(),  # type: ignore[arg-type]
            reference_acquirer=acquirer,  # type: ignore[arg-type]
        )

        result = service.run("12345")["result"]

        self.assertEqual(1, acquirer.calls)
        self.assertEqual(0, verifier.calls)
        self.assertEqual("not_checked", result["variantStatus"])
        self.assertIn("reference_download_failed", result["variantReasons"])

    def test_existing_reference_does_not_trigger_acquisition(self) -> None:
        verifier = _CountingVerifier()
        acquirer = _FakeAcquirer(error=AssertionError("acquirer should not run"))
        service = VariantDetectionService(
            database_path=self.db,
            audio_verifier=verifier,  # type: ignore[arg-type]
            reference_resolver=_ExistingResolver(self.reference),  # type: ignore[arg-type]
            reference_acquirer=acquirer,  # type: ignore[arg-type]
        )

        result = service.run("12345")["result"]

        self.assertEqual(0, acquirer.calls)
        self.assertEqual(1, verifier.calls)
        self.assertEqual(str(self.reference), result["referencePath"])

    def test_yandex_download_provider_uses_download_info_direct_link_method(self) -> None:
        provider = YandexMusicDownloadProvider(token="test-token")
        provider._build_client = lambda: _FakeClient()  # type: ignore[method-assign]
        link = provider._resolve_direct_link("12345", quality="best")
        self.assertEqual("https://example.invalid/reference.mp3", link)


if __name__ == "__main__":
    unittest.main()
