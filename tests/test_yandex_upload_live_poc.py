"""Offline tests for the explicit Yandex single-track upload PoC runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_live_poc.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_live_poc", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
poc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(poc)


class YandexUploadLivePocTests(unittest.TestCase):
    def test_single_new_readback_id_is_verified(self) -> None:
        result = poc._classify_readback_identity({"1", "2"}, {"1", "2", "3"}, None)  # noqa: SLF001
        self.assertTrue(result["verified"])
        self.assertEqual(result["verifiedTrackId"], "3")
        self.assertEqual(result["identitySource"], "single-readback-difference")
        self.assertFalse(result["ambiguous"])

    def test_multiple_new_ids_without_stage2_identity_are_not_verified(self) -> None:
        result = poc._classify_readback_identity({"1"}, {"1", "2", "3"}, None)  # noqa: SLF001
        self.assertFalse(result["verified"])
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["newTrackIds"], ["2", "3"])

    def test_stage2_track_id_resolves_multiple_readback_ids(self) -> None:
        result = poc._classify_readback_identity({"1"}, {"1", "2", "3"}, "3")  # noqa: SLF001
        self.assertTrue(result["verified"])
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["verifiedTrackId"], "3")
        self.assertEqual(result["identitySource"], "stage2-track-id")

    def test_existing_reported_track_id_does_not_verify_upload(self) -> None:
        result = poc._classify_readback_identity({"1", "2"}, {"1", "2"}, "2")  # noqa: SLF001
        self.assertFalse(result["verified"])
        self.assertEqual(result["identitySource"], "not-observed")


if __name__ == "__main__":
    unittest.main()
