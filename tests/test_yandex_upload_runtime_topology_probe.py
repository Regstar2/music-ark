"""Offline tests for numeric webpack upload/runtime topology analysis."""

from __future__ import annotations

from collections import defaultdict
import importlib.util
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_runtime_topology_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_runtime_topology_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadRuntimeTopologyProbeTests(unittest.TestCase):
    def test_undirected_path_connects_config_and_request_through_composition_root(self) -> None:
        graph = defaultdict(set, {
            "900": {"31322", "7644"},
            "12690": {"31322"},
        })
        path = probe._undirected_path(graph, "31322", "7644")  # noqa: SLF001
        self.assertEqual(path, ["31322", "900", "7644"])

    def test_common_importer_ranks_nearest_composition_root(self) -> None:
        graph = defaultdict(set, {
            "900": {"31322", "7644"},
            "901": {"900"},
        })
        common = probe._common_importers(graph, "31322", "7644")  # noqa: SLF001
        self.assertEqual(common[0], {"module_id": "900", "distance_to_left": 1, "distance_to_right": 1})

    def test_topology_report_exposes_only_numeric_module_structure(self) -> None:
        graph = defaultdict(set, {
            "12690": {"31322"},
            "900": {"31322", "7644"},
        })
        metadata = {
            "31322": {
                "anchors": {"createHttpOptions", "createRequestHeaders"},
                "properties": {"authorization", "prefixUrl"},
                "member_paths": {"app/chunk.js"},
            },
            "7644": {
                "anchors": set(),
                "properties": {"customApiPrefixUrl", "customApiToken"},
                "member_paths": {"app/config.js"},
            },
        }
        report = probe.topology_report(graph, metadata)
        request = next(item for item in report["target_modules"] if item["module_id"] == "31322")
        self.assertIn("12690", request["direct_importers"])
        self.assertIn("900", request["direct_importers"])
        pair = next(item for item in report["target_pairs"] if item["left"] == "31322" and item["right"] == "7644")
        self.assertEqual(pair["undirected_path"], ["31322", "900", "7644"])

    def test_missing_pair_does_not_invent_path(self) -> None:
        graph = defaultdict(set, {"12690": {"31322"}, "7644": set()})
        self.assertIsNone(probe._undirected_path(graph, "31322", "7644"))  # noqa: SLF001
        self.assertEqual(probe._common_importers(graph, "31322", "7644"), [])  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
