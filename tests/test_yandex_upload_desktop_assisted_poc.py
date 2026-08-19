"""Offline tests for the official-desktop-assisted upload verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_desktop_assisted_poc.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_desktop_assisted_poc", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
poc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(poc)


class YandexUploadDesktopAssistedPocTests(unittest.TestCase):
    def test_exactly_one_new_id_verifies(self) -> None:
        snapshots = iter([{"1", "2"}, {"1", "2", "3"}])
        with patch.object(poc.time, "sleep"):
            result = poc.verify_readback(
                before_ids={"1", "2"},
                read_current_ids=lambda: next(snapshots),
                attempts=2,
                delay=0,
            )
        self.assertTrue(result["verified"])
        self.assertEqual(result["verifiedTrackId"], "3")
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["attemptsUsed"], 2)

    def test_multiple_new_ids_are_ambiguous(self) -> None:
        result = poc.verify_readback(
            before_ids={"1"},
            read_current_ids=lambda: {"1", "2", "3"},
            attempts=5,
            delay=0,
        )
        self.assertFalse(result["verified"])
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["newTrackIds"], ["2", "3"])
        self.assertEqual(result["attemptsUsed"], 1)

    def test_polling_is_bounded_when_nothing_changes(self) -> None:
        calls = []

        def read_current_ids():
            calls.append(1)
            return {"1"}

        with patch.object(poc.time, "sleep"):
            result = poc.verify_readback(
                before_ids={"1"},
                read_current_ids=read_current_ids,
                attempts=3,
                delay=0.1,
            )
        self.assertFalse(result["verified"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["attemptsUsed"], 3)

    def test_verifier_never_calls_upload_transport(self) -> None:
        source = _TOOL.read_text(encoding="utf-8")
        self.assertNotIn("upload_file(", source)
        self.assertNotIn("prepare_upload(", source)
        self.assertNotIn("MUSICARK_YANDEX_UPLOAD_LIVE", source)
        self.assertIn('"initiatedByMusicArk": False', source)
        self.assertIn('"singleFileOnly": True', source)


if __name__ == "__main__":
    unittest.main()
