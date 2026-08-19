"""Offline tests for normalized stage-one playlist-id dataflow."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_playlist_id_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_playlist_id_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1PlaylistIdProbeTests(unittest.TestCase):
    def test_normalized_expression_preserves_semantics_and_hashes_locals(self) -> None:
        tokens = probe._normalize_expression(  # noqa: SLF001
            "53128",
            'helper(uidLocal, playlistKind, "PRIVATE")',
            [],
        )
        encoded = json.dumps(tokens)
        self.assertIn("playlistKind", tokens)
        self.assertIn("<string>", tokens)
        self.assertNotIn("uidLocal", encoded)
        self.assertNotIn("PRIVATE", encoded)
        self.assertTrue(any(str(item).startswith("alias:") for item in tokens))

    def test_template_interpolation_keeps_safe_semantics_not_literal(self) -> None:
        tokens = probe._normalize_expression(  # noqa: SLF001
            "10",
            '`private-prefix-${uid}-${playlistKind}`',
            [],
        )
        encoded = json.dumps(tokens)
        self.assertIn("<template>", tokens)
        self.assertIn("uid", tokens)
        self.assertIn("playlistKind", tokens)
        self.assertNotIn("private-prefix", encoded)

    def test_call_record_reports_alias_relationship_and_nearest_assignment(self) -> None:
        body = (
            "const accountUid=user.uid;"
            "const computed=makeId(accountUid,playlistKind);"
            "api.getUploadUrl({playlistId:computed,playlistKind:playlistKind,uid:accountUid,path:file.name});"
        )
        records = probe._call_records("53128", body)  # noqa: SLF001
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertTrue(record["relationships"]["playlistIdSharesAliasWithUid"])
        assignments = record["playlistId"]["aliasAssignments"]
        encoded = json.dumps(assignments)
        self.assertNotIn("computed", encoded)
        self.assertNotIn("accountUid", encoded)
        self.assertIn("playlistKind", json.dumps(record["playlistId"]))

    def test_object_values_keep_only_protocol_keys(self) -> None:
        values = probe._safe_object_values(  # noqa: SLF001
            "{playlistId:a,playlistKind:b,uid:c,path:d,ordinarySecret:e}"
        )
        self.assertEqual(set(values), {"playlistId", "playlistKind", "uid", "path"})
        self.assertNotIn("ordinarySecret", json.dumps(values))

    def test_method_definition_or_zero_arg_call_is_ignored(self) -> None:
        self.assertEqual(probe._call_records("1", "class X{getUploadUrl(a){}}"), [])  # noqa: SLF001
        self.assertEqual(probe._call_records("1", "api.getUploadUrl()"), [])  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
