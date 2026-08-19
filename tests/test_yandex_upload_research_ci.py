"""Offline tests for the centralized Yandex upload research orchestrator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_research_ci.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_research_ci", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
research = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(research)


class YandexUploadResearchCiTests(unittest.TestCase):
    def _report(self):
        safety = {key: False for key in research._REQUIRED_FALSE_SAFETY_FLAGS}  # noqa: SLF001
        safety["raw_local_identifiers_included"] = False
        return {"input_sha256": "abc", "safety": safety}

    def test_valid_report_passes_all_safety_gates(self) -> None:
        research.validate_report(self._report(), expected_sha256="abc")

    def test_hash_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            research.validate_report(self._report(), expected_sha256="def")

    def test_missing_or_true_required_safety_flag_is_rejected(self) -> None:
        report = self._report()
        report["safety"]["credential_values_included"] = True
        with self.assertRaisesRegex(ValueError, "credential_values_included"):
            research.validate_report(report, expected_sha256="abc")

    def test_optional_identifier_flag_must_be_false_when_present(self) -> None:
        report = self._report()
        report["safety"]["raw_local_identifiers_included"] = True
        with self.assertRaisesRegex(ValueError, "raw_local_identifiers_included"):
            research.validate_report(report, expected_sha256="abc")

    def test_pipeline_registry_includes_v21(self) -> None:
        names = [name for name, _ in research._PROBES]  # noqa: SLF001
        self.assertIn("yandex-upload-prefix-provenance-v21-ci.json", names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
