from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from musicark.audio.conversion import AudioConversionError, YandexAudioConversionService
from musicark.audio.ffmpeg import FFmpegLocator, FFmpegRunner
from musicark.audio.formats import AUDIO_FORMAT_CAPABILITIES, capabilities_for_extension
from musicark.metadata.formats.registry import MetadataAdapterRegistry


_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cff00000040101f61738550000000049454e44ae426082"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_wav(path: Path, *, seconds: float = 1.25) -> None:
    rate = 44100
    frames = int(rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        for index in range(frames):
            sample = int(9000 * math.sin(2 * math.pi * 440 * index / rate))
            handle.writeframesraw(struct.pack("<hh", sample, sample))


class _SyntheticAudio:
    def __init__(self, root: Path) -> None:
        self.root = root
        resolution = FFmpegLocator().resolve()
        if not resolution.available or resolution.executable is None:
            raise AssertionError(f"FFmpeg unavailable for v0.13 tests: {resolution.status.value}")
        self.runner = FFmpegRunner(resolution.executable)
        self.wav = root / "source.wav"
        _write_wav(self.wav)

    def make(self, extension: str, *, name: str = "track") -> Path:
        extension = extension.casefold()
        path = self.root / f"{name}{extension}"
        codecs = {
            ".mp3": ["-c:a", "libmp3lame", "-q:a", "3"],
            ".flac": ["-c:a", "flac"],
            ".m4a": ["-c:a", "aac", "-b:a", "160k"],
            ".aac": ["-c:a", "aac", "-b:a", "160k", "-f", "adts"],
            ".ogg": ["-c:a", "libvorbis", "-q:a", "4"],
            ".opus": ["-c:a", "libopus", "-b:a", "128k"],
            ".wav": ["-c:a", "pcm_s16le"],
        }
        result = self.runner.run(
            ["-y", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(self.wav), *codecs[extension], str(path)],
            timeout_seconds=60,
        )
        self.assert_success(result.return_code, result.stderr)
        if not path.is_file() or path.stat().st_size <= 0:
            raise AssertionError(f"Synthetic fixture was not created: {path}")
        return path

    @staticmethod
    def assert_success(return_code: int, stderr: str) -> None:
        if return_code != 0:
            raise AssertionError(f"FFmpeg fixture generation failed: {stderr[-2000:]}")


class FormatCapabilityTests(unittest.TestCase):
    def test_registry_is_single_fail_closed_source_for_all_required_extensions(self):
        expected = {".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"}
        actual = {extension for item in AUDIO_FORMAT_CAPABILITIES for extension in item.extensions}
        self.assertEqual(expected, actual)
        self.assertIsNone(capabilities_for_extension(".wma"))
        self.assertIsNone(capabilities_for_extension(""))

    def test_direct_upload_only_mp3_and_all_other_required_formats_convert(self):
        mp3 = capabilities_for_extension(".mp3")
        self.assertIsNotNone(mp3)
        assert mp3 is not None
        self.assertTrue(mp3.can_upload_directly)
        self.assertFalse(mp3.can_transcode_for_yandex)
        for extension in (".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"):
            capability = capabilities_for_extension(extension)
            self.assertIsNotNone(capability)
            assert capability is not None
            self.assertFalse(capability.can_upload_directly)
            self.assertTrue(capability.can_transcode_for_yandex)

    def test_aac_and_wav_are_explicitly_read_only(self):
        for extension in (".aac", ".wav"):
            capability = capabilities_for_extension(extension)
            assert capability is not None
            self.assertTrue(capability.can_read_metadata)
            self.assertFalse(capability.can_write_metadata)
            self.assertFalse(capability.can_write_artwork)


class MetadataAdapterTests(unittest.TestCase):
    def test_writable_formats_round_trip_normalized_fields_and_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = _SyntheticAudio(Path(tmp))
            registry = MetadataAdapterRegistry()
            for extension in (".mp3", ".flac", ".m4a", ".ogg", ".opus"):
                with self.subTest(extension=extension):
                    path = fixtures.make(extension, name=f"roundtrip-{extension[1:]}")
                    adapter = registry.writable_adapter_for(path)
                    self.assertIsNotNone(adapter)
                    assert adapter is not None
                    adapter.apply(
                        path,
                        {
                            "title": "Synthetic title",
                            "artists": ["Synthetic artist"],
                            "album": "Synthetic album",
                            "albumArtists": ["Synthetic album artist"],
                            "trackNumber": 2,
                            "totalTracks": 9,
                            "discNumber": 1,
                            "totalDiscs": 2,
                            "releaseDate": "2026-08-21",
                            "genres": ["Test"],
                        },
                        artwork_data=_PNG_1X1,
                        artwork_mime="image/png",
                    )
                    reopened = adapter.read(path)["fields"]
                    self.assertEqual("Synthetic title", reopened["title"])
                    self.assertIn("Synthetic artist", reopened["artists"])
                    self.assertEqual("Synthetic album", reopened["album"])
                    self.assertEqual(2, reopened["trackNumber"])
                    self.assertEqual(1, reopened["discNumber"])
                    artwork = adapter.artwork(path)
                    self.assertIsNotNone(artwork)
                    assert artwork is not None
                    self.assertEqual(_PNG_1X1, artwork[0])

    def test_read_only_formats_reject_writes_without_touching_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = _SyntheticAudio(Path(tmp))
            registry = MetadataAdapterRegistry()
            for extension in (".aac", ".wav"):
                with self.subTest(extension=extension):
                    path = fixtures.make(extension, name=f"readonly-{extension[1:]}")
                    before = _sha256(path)
                    self.assertIsNone(registry.writable_adapter_for(path))
                    adapter = registry.adapter_for(path)
                    self.assertIsNotNone(adapter)
                    assert adapter is not None
                    with self.assertRaises(Exception):
                        adapter.apply(path, {"title": "must not write"})
                    self.assertEqual(before, _sha256(path))


class ConversionTests(unittest.TestCase):
    def test_all_required_non_mp3_formats_convert_to_valid_temporary_mp3_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = _SyntheticAudio(root / "fixtures")
            service = YandexAudioConversionService(base_dir=root)
            for extension in (".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav"):
                with self.subTest(extension=extension):
                    path = fixtures.make(extension, name=f"source-{extension[1:]}")
                    before = _sha256(path)
                    prepared = service.prepare(path)
                    self.assertTrue(prepared.conversion_required)
                    self.assertEqual(".mp3", prepared.upload_path.suffix.casefold())
                    self.assertTrue(prepared.upload_path.is_file())
                    self.assertGreater(prepared.upload_path.stat().st_size, 0)
                    work_dir = prepared.upload_path.parent
                    self.assertTrue(prepared.upload_path.resolve().is_relative_to(service.temp_root.resolve()))
                    self.assertEqual(before, _sha256(path))
                    prepared.cleanup()
                    self.assertFalse(work_dir.exists())
                    self.assertEqual(before, _sha256(path))

    def test_mp3_is_direct_and_never_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = _SyntheticAudio(root / "fixtures")
            source = fixtures.make(".mp3")
            service = YandexAudioConversionService(base_dir=root)
            prepared = service.prepare(source)
            self.assertFalse(prepared.conversion_required)
            self.assertEqual(source.resolve(), prepared.upload_path)
            prepared.cleanup()
            self.assertTrue(source.is_file())

    def test_spaces_cyrillic_and_unicode_paths_are_arguments_not_shell_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "папка с пробелами ♫"
            fixtures = _SyntheticAudio(root)
            source = fixtures.make(".flac", name="трек тест ♫")
            service = YandexAudioConversionService(base_dir=Path(tmp))
            before = _sha256(source)
            with service.prepare(source) as prepared:
                self.assertTrue(prepared.upload_path.is_file())
            self.assertEqual(before, _sha256(source))

    def test_corrupted_supported_input_fails_closed_and_leaves_no_temp_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "broken.flac"
            source.write_bytes(b"not a flac")
            before = _sha256(source)
            service = YandexAudioConversionService(base_dir=root)
            with self.assertRaises(AudioConversionError):
                service.prepare(source)
            self.assertEqual(before, _sha256(source))
            self.assertEqual([], list(service.temp_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
