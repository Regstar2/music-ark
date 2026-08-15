from __future__ import annotations

import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from musicark.variant.audio import FfmpegAudioDecoder


class BundledAudioDecoderTests(unittest.TestCase):
    def test_packaged_ffmpeg_is_preferred_over_system_path(self) -> None:
        packaged = r"C:\MusicArk\runtime\ffmpeg.exe"
        fake_module = SimpleNamespace(get_ffmpeg_exe=lambda: packaged)
        with patch.dict(sys.modules, {"imageio_ffmpeg": fake_module}):
            with patch("musicark.variant.audio.shutil.which") as system_which:
                decoder = FfmpegAudioDecoder()

        self.assertTrue(decoder.available)
        self.assertEqual(packaged, decoder._executable)
        system_which.assert_not_called()

    def test_system_ffmpeg_remains_dev_fallback_if_packaged_runtime_is_missing(self) -> None:
        fake_module = SimpleNamespace(get_ffmpeg_exe=lambda: (_ for _ in ()).throw(RuntimeError("missing")))
        with patch.dict(sys.modules, {"imageio_ffmpeg": fake_module}):
            with patch("musicark.variant.audio.shutil.which", return_value="ffmpeg") as system_which:
                decoder = FfmpegAudioDecoder()

        self.assertTrue(decoder.available)
        self.assertEqual("ffmpeg", decoder._executable)
        system_which.assert_called_once_with("ffmpeg")

    def test_explicit_empty_executable_can_simulate_unavailable_decoder(self) -> None:
        decoder = FfmpegAudioDecoder(executable="")
        self.assertFalse(decoder.available)


if __name__ == "__main__":
    unittest.main()
