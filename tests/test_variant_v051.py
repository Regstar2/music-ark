from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.storage.database import initialize_database
from musicark.variant.audio import AudioAligner, AudioDecodeError, SegmentComparator
from musicark.variant.classifier import VariantClassifier
from musicark.variant.metadata import MetadataVariantDetector, extract_variant_markers
from musicark.variant.models import AudioComparison, DecodedAudio, ReferenceAudio, VariantStatus
from musicark.variant.policy import SAMPLE_RATE
from musicark.variant.reference import (
    ReferenceAcquisitionError,
    ReferenceAudioResolver,
    strict_yandex_id_from_path,
)
from musicark.variant.service import VariantDetectionService


def synthetic_audio(seconds: float = 24.0, *, gain: float = 1.0) -> DecodedAudio:
    count = int(SAMPLE_RATE * seconds)
    samples: list[int] = []
    for index in range(count):
        t = index / SAMPLE_RATE
        envelope = 0.30 + 0.25 * (1.0 + math.sin(2.0 * math.pi * 0.31 * t))
        envelope += 0.12 * math.sin(2.0 * math.pi * 0.07 * t + 0.4)
        signal = (
            math.sin(2.0 * math.pi * 220.0 * t)
            + 0.48 * math.sin(2.0 * math.pi * 443.0 * t + 0.3)
            + 0.16 * math.sin(2.0 * math.pi * 997.0 * t)
        )
        samples.append(int(max(-1.0, min(1.0, signal * envelope * 0.38 * gain)) * 32767))
    return DecodedAudio(tuple(samples), SAMPLE_RATE)


def replace_segment(audio: DecodedAudio, start: float, end: float, *, mode: str) -> DecodedAudio:
    samples = list(audio.samples)
    first = int(start * audio.sample_rate)
    last = min(len(samples), int(end * audio.sample_rate))
    for index in range(first, last):
        if mode == "silence":
            samples[index] = 0
        else:
            t = index / audio.sample_rate
            samples[index] = int(math.sin(2.0 * math.pi * 1800.0 * t) * 20000)
    return DecodedAudio(tuple(samples), audio.sample_rate)


class VariantAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.comparator = SegmentComparator()
        self.classifier = VariantClassifier()
        self.metadata = MetadataVariantDetector()

    def _evidence(self, *, provider_title: str = "Song", local_title: str = "Song", explicit=None):
        provider = {
            "title": provider_title,
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 24.0,
            "explicit": explicit,
        }
        local = {
            "title": local_title,
            "artists": ["Artist"],
            "album": "Album",
            "duration_seconds": 24.0,
            "path": f"{local_title}.flac",
            "metadata": {},
        }
        return self.metadata.analyze(provider, local)

    def test_identical_synthetic_signal_is_same(self) -> None:
        audio = synthetic_audio()
        comparison = self.comparator.compare(
            audio,
            audio,
            offset_seconds=0.0,
            alignment_confidence=1.0,
        )
        status, _ = self.classifier.classify(
            self._evidence(),
            comparison,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertEqual(VariantStatus.SAME, status)
        self.assertGreater(comparison.global_similarity, 0.99)

    def test_gain_and_quantization_difference_stays_same(self) -> None:
        reference = synthetic_audio()
        changed = DecodedAudio(
            tuple(int(round(value * 0.72 / 64.0) * 64) for value in reference.samples),
            reference.sample_rate,
        )
        comparison = self.comparator.compare(
            reference,
            changed,
            offset_seconds=0.0,
            alignment_confidence=1.0,
        )
        status, _ = self.classifier.classify(
            self._evidence(),
            comparison,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertEqual(VariantStatus.SAME, status)

    def test_two_seconds_of_silence_are_altered(self) -> None:
        reference = synthetic_audio()
        local = replace_segment(reference, 10.0, 12.0, mode="silence")
        comparison = self.comparator.compare(
            reference,
            local,
            offset_seconds=0.0,
            alignment_confidence=1.0,
        )
        status, reasons = self.classifier.classify(
            self._evidence(explicit=True),
            comparison,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertEqual(VariantStatus.ALTERED, status)
        self.assertTrue(comparison.altered_regions)
        self.assertIn("localized_audio_differences", reasons)
        self.assertIn("possible_clean_or_censored_variant", reasons)

    def test_short_replacement_tone_is_altered(self) -> None:
        reference = synthetic_audio()
        local = replace_segment(reference, 5.0, 7.0, mode="tone")
        comparison = self.comparator.compare(
            reference,
            local,
            offset_seconds=0.0,
            alignment_confidence=1.0,
        )
        status, _ = self.classifier.classify(
            self._evidence(),
            comparison,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertEqual(VariantStatus.ALTERED, status)

    def test_large_audio_change_is_not_same(self) -> None:
        reference = synthetic_audio()
        local = replace_segment(reference, 2.0, 22.0, mode="tone")
        comparison = self.comparator.compare(
            reference,
            local,
            offset_seconds=0.0,
            alignment_confidence=1.0,
        )
        status, _ = self.classifier.classify(
            self._evidence(),
            comparison,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertIn(status, {VariantStatus.DIFFERENT_VERSION, VariantStatus.UNCERTAIN})
        self.assertNotEqual(VariantStatus.SAME, status)

    def test_small_start_offset_aligns_same_recording(self) -> None:
        reference = synthetic_audio()
        pad = (0,) * SAMPLE_RATE
        local = DecodedAudio(pad + reference.samples, SAMPLE_RATE)
        offset, confidence = AudioAligner().align(reference, local)
        self.assertAlmostEqual(1.0, offset, delta=0.5)
        self.assertGreater(confidence, 0.5)
        comparison = self.comparator.compare(
            reference,
            local,
            offset_seconds=offset,
            alignment_confidence=confidence,
        )
        self.assertGreater(comparison.global_similarity, 0.94)

    def test_significant_shorter_duration_is_different_or_uncertain(self) -> None:
        comparison = AudioComparison(0.0, 1.0, 0.91, 0.93, 0.08, (), 20)
        status, _ = self.classifier.classify(
            self._evidence(),
            comparison,
            provider_duration=24.0,
            local_duration=15.0,
            reference_available=True,
            audio_available=True,
        )
        self.assertIn(status, {VariantStatus.DIFFERENT_VERSION, VariantStatus.UNCERTAIN})

    def test_semantic_markers_never_auto_same(self) -> None:
        for marker in ("Live", "Remix", "Acoustic", "Instrumental", "Radio Edit"):
            with self.subTest(marker=marker):
                evidence = self._evidence(local_title=f"Song ({marker})")
                status, _ = self.classifier.classify(
                    evidence,
                    None,
                    provider_duration=24.0,
                    local_duration=24.0,
                    reference_available=False,
                    audio_available=False,
                )
                self.assertNotEqual(VariantStatus.SAME, status)

    def test_explicit_mismatch_without_audio_does_not_claim_censorship(self) -> None:
        provider = {
            "title": "Song",
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 24,
            "explicit": True,
        }
        local = {
            "title": "Song",
            "artists": ["Artist"],
            "album": "Album",
            "duration_seconds": 24,
            "path": "Song.flac",
            "metadata": {"explicit": False},
        }
        evidence = self.metadata.analyze(provider, local)
        status, reasons = self.classifier.classify(
            evidence,
            None,
            provider_duration=24.0,
            local_duration=24.0,
            reference_available=False,
            audio_available=False,
        )
        self.assertEqual(VariantStatus.UNCERTAIN, status)
        self.assertNotIn("possible_clean_or_censored_variant", reasons)

    def test_marker_extraction_includes_required_vocabulary(self) -> None:
        markers = extract_variant_markers(
            "Song (Live Remix Acoustic Instrumental Remastered Radio Edit Clean Explicit Censored Uncensored)"
        )
        for expected in (
            "live", "remix", "acoustic", "instrumental", "remastered",
            "radio edit", "clean", "explicit", "censored", "uncensored",
        ):
            self.assertIn(expected, markers)


class _FixedReferenceResolver:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    def resolve(self, provider_id: str, external_id: str) -> ReferenceAudio | None:
        if self.path is None:
            return None
        return ReferenceAudio(self.path, provider_id, external_id)


class _UnavailableReferenceAcquirer:
    def acquire(self, provider_id: str, external_id: str) -> ReferenceAudio:
        raise ReferenceAcquisitionError("reference not found in isolated unit test")


class _CountingVerifier:
    def __init__(self, *, available: bool = True, fail: Exception | None = None) -> None:
        self.available = available
        self.fail = fail
        self.calls = 0

    def compare(self, reference_path: Path, local_path: Path) -> AudioComparison:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return AudioComparison(0.0, 1.0, 0.99, 0.99, 0.0, (), 20)


class VariantServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        initialize_database(self.db)
        self.local = self.root / "Song.flac"
        self.reference = self.root / "yandex_69046542.mp3"
        self.local.write_bytes(b"local-test-audio")
        self.reference.write_bytes(b"reference-test-audio")
        self._seed_matched_pair()

    def _seed_matched_pair(self) -> None:
        local_stat = self.local.stat()
        provider = {
            "provider_id": "yandex_music",
            "external_id": "69046542",
            "title": "Song",
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 24,
            "explicit": False,
        }
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT INTO provider_tracks(provider_id, external_id, payload_json) VALUES (?, ?, ?)",
                ("yandex_music", "69046542", json.dumps(provider)),
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
                    str(self.local), "legacy-hash", local_stat.st_size, 24.0, "flac", "{}",
                    local_stat.st_mtime_ns, "Song", '["Artist"]', "Album", "available",
                    str(self.local).casefold(), self.local.name, ".flac",
                ),
            )
            local_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO matching_results(
                    provider_id, external_id, status, local_file_id, confidence,
                    method, score_breakdown_json, reason, matcher_version,
                    provider_fingerprint, local_fingerprint, manual
                ) VALUES (?, ?, 'matched', ?, 0.99, 'manual', '{}', 'manual_accept', 1, 'p', 'l', 1)
                """,
                ("yandex_music", "69046542", local_id),
            )
            conn.commit()

    def _service(self, verifier: _CountingVerifier, reference: Path | None = None) -> VariantDetectionService:
        return VariantDetectionService(
            database_path=self.db,
            provider_id="yandex_music",
            audio_verifier=verifier,  # type: ignore[arg-type]
            reference_resolver=_FixedReferenceResolver(reference),  # type: ignore[arg-type]
            reference_acquirer=_UnavailableReferenceAcquirer(),  # type: ignore[arg-type]
        )

    def test_reference_missing_is_not_checked(self) -> None:
        service = self._service(_CountingVerifier(), None)
        result = service.run("69046542")["result"]
        self.assertEqual("not_checked", result["variantStatus"])
        self.assertIn("reference_unavailable", result["variantReasons"])

    def test_decoder_unavailable_is_graceful(self) -> None:
        verifier = _CountingVerifier(available=False)
        service = self._service(verifier, self.reference)
        result = service.run("69046542")["result"]
        self.assertEqual("not_checked", result["variantStatus"])
        self.assertIn("audio_decoder_unavailable", result["variantReasons"])
        self.assertEqual(0, verifier.calls)

    def test_corrupted_file_error_is_uncertain_not_different(self) -> None:
        verifier = _CountingVerifier(fail=AudioDecodeError("corrupted input"))
        service = self._service(verifier, self.reference)
        result = service.run("69046542")["result"]
        self.assertEqual("uncertain", result["variantStatus"])
        self.assertIn("decode_error", result["variantReasons"])

    def test_unchanged_fingerprints_skip_second_decode(self) -> None:
        verifier = _CountingVerifier()
        service = self._service(verifier, self.reference)
        first = service.run("69046542")
        second = service.run("69046542")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(1, verifier.calls)

    def test_local_change_invalidates_cached_variant(self) -> None:
        verifier = _CountingVerifier()
        service = self._service(verifier, self.reference)
        service.run("69046542")
        self.local.write_bytes(b"local-test-audio-changed-and-longer")
        service.run("69046542")
        self.assertEqual(2, verifier.calls)

    def test_reference_change_invalidates_cached_variant(self) -> None:
        verifier = _CountingVerifier()
        service = self._service(verifier, self.reference)
        service.run("69046542")
        self.reference.write_bytes(b"reference-test-audio-changed-and-longer")
        service.run("69046542")
        self.assertEqual(2, verifier.calls)

    def test_strict_reference_filename_convention(self) -> None:
        self.assertEqual("69046542", strict_yandex_id_from_path(Path("yandex_69046542.mp3")))
        self.assertEqual("69046542", strict_yandex_id_from_path(Path("yandex-69046542.flac")))
        self.assertIsNone(strict_yandex_id_from_path(Path("song_69046542.mp3")))
        self.assertIsNone(strict_yandex_id_from_path(Path("artist/69046542/song.mp3")))

    def test_default_reference_resolver_does_not_use_incidental_numbers(self) -> None:
        unrelated = self.root / "Artist 69046542 - Song.mp3"
        unrelated.write_bytes(b"x")
        with sqlite3.connect(self.db) as conn:
            stat = unrelated.stat()
            conn.execute(
                """
                INSERT INTO local_audio_files(path, sha256, file_size, duration_seconds, codec,
                    metadata_json, modified_ns, title, artists_json, availability, normalized_path,
                    file_name, extension)
                VALUES (?, 'x', ?, 24, 'mp3', '{}', ?, 'Other', '[]', 'available', ?, ?, '.mp3')
                """,
                (str(unrelated), stat.st_size, stat.st_mtime_ns, str(unrelated).casefold(), unrelated.name),
            )
            conn.commit()
        resolver = ReferenceAudioResolver(self.db, self.root)
        self.assertIsNone(resolver.resolve("yandex_music", "69046542"))

    def test_migration_14_to_15_preserves_existing_data(self) -> None:
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO provider_collection_snapshots(provider_id, collection_id, account_json, item_count, refreshed_at) VALUES ('yandex_music', 'liked', '{}', 1, 'now')"
            )
            conn.execute(
                "INSERT OR REPLACE INTO provider_collection_items(provider_id, collection_id, external_id, position, payload_json) VALUES ('yandex_music', 'liked', 'keep-me', 0, '{}')"
            )
            conn.execute("DROP TABLE track_variant_results")
            conn.execute("UPDATE app_metadata SET value='1.4.0' WHERE key='schema_version'")
            conn.commit()

        initialize_database(self.db)

        with sqlite3.connect(self.db) as conn:
            version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
            provider_count = conn.execute("SELECT COUNT(*) FROM provider_collection_items WHERE external_id='keep-me'").fetchone()[0]
            local_count = conn.execute("SELECT COUNT(*) FROM local_audio_files").fetchone()[0]
            matching = conn.execute(
                "SELECT status, manual FROM matching_results WHERE provider_id='yandex_music' AND external_id='69046542'"
            ).fetchone()
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='track_variant_results'"
            ).fetchone()
        self.assertEqual("1.6.0", version)
        self.assertEqual(1, provider_count)
        self.assertGreaterEqual(local_count, 1)
        self.assertEqual(("matched", 1), matching)
        self.assertIsNotNone(table)


if __name__ == "__main__":
    unittest.main()
