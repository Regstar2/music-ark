"""Tests for configuration load/save behavior."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.core.config import AppConfig, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_load_config_creates_default_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            config = load_config(base_dir)

            self.assertEqual(config.database_path, ".musicark/musicark.db")
            self.assertTrue((base_dir / ".musicark" / "config.json").exists())

    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            expected = AppConfig(database_path="data/custom.db", log_level="DEBUG")
            save_config(expected, base_dir)

            actual = load_config(base_dir)
            self.assertEqual(actual.database_path, "data/custom.db")
            self.assertEqual(actual.log_level, "DEBUG")


if __name__ == "__main__":
    unittest.main()
