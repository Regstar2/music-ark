"""Offline tests for stage-one playlist/upload-center call-site tracing."""

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

_TOOL = _TOOLS / "yandex_upload_stage1_flow_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_stage1_flow_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadStage1FlowProbeTests(unittest.TestCase):
    def test_get_upload_url_traces_playlist_id_to_upload_center_semantics(self) -> None:
        body = (
            "const hiddenPlaylist=state.uploadCenterPlaylistId;"
            "client.getUploadUrl({uid:user.uid,playlistId:hiddenPlaylist,playlistKind:target.kind,path:file.name});"
        )
        result = probe.analyze_module("500", body)
        self.assertIsNotNone(result)
        assert result is not None
        call = next(item for item in result["calls"] if item["method"] == "getUploadUrl")
        properties = call["arguments"][0]["objectProperties"]
        playlist = next(item for item in properties if item["key"] == "playlistId")
        assignment = playlist["value"]["nearestAssignment"]
        self.assertIn("uploadCenterPlaylistId", assignment["semanticNames"])
        self.assertTrue(result["uploadCenterEvidence"])
        encoded = json.dumps(result)
        self.assertNotIn("hiddenPlaylist", encoded)

    def test_target_playlist_lifecycle_is_kept_separate_from_stage1_source(self) -> None:
        body = (
            "const slot=uploadCenter.id;"
            "api.getUploadUrl({playlistId:slot,playlistKind:playlist.kind,uid:account.uid,path:file.name});"
            "api.moveTracksFromUploadCenterToPlaylist({playlistId:playlist.id,playlistKind:playlist.kind,trackIds:tracks});"
            "api.checkProcessingTracks({trackIds:tracks});"
        )
        result = probe.analyze_module("700", body)
        self.assertIsNotNone(result)
        assert result is not None
        methods = [item["method"] for item in result["calls"]]
        self.assertIn("getUploadUrl", methods)
        self.assertIn("moveTracksFromUploadCenterToPlaylist", methods)
        self.assertIn("checkProcessingTracks", methods)
        self.assertTrue(result["uploadCenterEvidence"])

    def test_import_refs_keep_module_and_export_without_local_alias(self) -> None:
        body = (
            "const provider=req(12345);"
            "client.getUploadUrl({playlistId:provider.uploadCenterId,path:file.name,uid:user.uid});"
        )
        result = probe.analyze_module("900", body)
        self.assertIsNotNone(result)
        assert result is not None
        call = result["calls"][0]
        playlist = next(item for item in call["arguments"][0]["objectProperties"] if item["key"] == "playlistId")
        self.assertEqual(
            playlist["value"]["sourceRefs"],
            [{"source_module_id": "12345", "export_key": "uploadCenterId"}],
        )
        self.assertNotIn("provider", json.dumps(result))

    def test_generic_keys_and_locals_are_hashed_and_strings_are_not_emitted(self) -> None:
        body = (
            'const privateAlias="DO_NOT_EMIT";'
            "client.getUploadUrl({playlistId:privateAlias,ordinaryField:privateAlias,path:file.name});"
        )
        result = probe.analyze_module("42", body)
        self.assertIsNotNone(result)
        assert result is not None
        encoded = json.dumps(result)
        self.assertNotIn("privateAlias", encoded)
        self.assertNotIn("ordinaryField", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        call = result["calls"][0]
        keys = [item["key"] for item in call["arguments"][0]["objectProperties"]]
        self.assertIn("playlistId", keys)
        self.assertTrue(any(key.startswith("key:") for key in keys))

    def test_method_definition_is_not_mislabeled_as_callsite(self) -> None:
        body = "class X{getUploadUrl(arg){return arg}}"
        self.assertIsNone(probe.analyze_module("10", body))


if __name__ == "__main__":
    unittest.main()
