"""Tests for metadata validation helpers (v0.10)."""

from __future__ import annotations

import unittest

from musicark.core.errors import MetadataEditorError
from musicark.metadata.engine import validate_text, validate_track_number, validate_year


class MetadataEngineValidationTests(unittest.TestCase):
    def test_validate_year_rejects_oob(self) -> None:
        with self.assertRaises(MetadataEditorError):
            validate_year(1700)

    def test_validate_year_optional(self) -> None:
        self.assertIsNone(validate_year(None))
        self.assertIsNone(validate_year(""))

    def test_validate_track_optional(self) -> None:
        self.assertIsNone(validate_track_number(None))
        self.assertEqual(validate_track_number(42), 42)

    def test_validate_text_length(self) -> None:
        with self.assertRaises(MetadataEditorError):
            validate_text("x", "a" * 600)


if __name__ == "__main__":
    unittest.main()
