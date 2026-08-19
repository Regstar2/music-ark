"""Offline tests for safe stage-one playlist-id literals."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_stage1_playlist_id_literal_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_playlist_id_literal_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1PlaylistIdLiteralProbeTests(unittest.TestCase):
    def test_empty_and_punctuation_strings_are_allowlisted(self) -> None:
        self.assertEqual(probe._safe_string_token('""'), {"kind": "empty-string"})  # noqa: SLF001
        self.assertEqual(  # noqa: SLF001
            probe._safe_string_token('":"'),
            {"kind": "punctuation-string", "value": ":"},
        )
        self.assertEqual(  # noqa: SLF001
            probe._safe_string_token('"PRIVATE"'),
            {"kind": "redacted-string"},
        )

    def test_formula_reveals_concat_and_safe_separator_only(self) -> None:
        tokens = probe._tokenize_formula(  # noqa: SLF001
            "53128",
            '"".concat(accountUid, ":").concat(item.playlistKind)',
            [],
        )
        encoded = json.dumps(tokens)
        self.assertIn("concat", tokens)
        self.assertIn("playlistKind", tokens)
        self.assertIn({"kind": "empty-string"}, tokens)
        self.assertIn({"kind": "punctuation-string", "value": ":"}, tokens)
        self.assertNotIn("accountUid", encoded)
        self.assertNotIn("item", encoded)

    def test_ordinary_literals_never_escape_formula_records(self) -> None:
        body = (
            'api.getUploadUrl({playlistId:"PRIVATE".concat(uid,"SECRET").concat(x.playlistKind),'
            "uid:uid,path:file.name});"
        )
        records = probe._formula_records("10", body)  # noqa: SLF001
        encoded = json.dumps(records)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertIn("redacted-string", encoded)

    def test_zero_arg_or_definition_is_ignored(self) -> None:
        self.assertEqual(probe._formula_records("1", "api.getUploadUrl()"), [])  # noqa: SLF001
        self.assertEqual(probe._formula_records("1", "class X{getUploadUrl(a){}}"), [])  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
