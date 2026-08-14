"""Bridge contract tests for MusicArk v0.4 Local Library commands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from musicark import mvp_bridge


class LocalLibraryBridgeV04Tests(unittest.TestCase):
    def args(self, command: str, **overrides: object) -> argparse.Namespace:
        values = {
            "command": command,
            "root_id": None,
            "track_id": None,
            "limit": 500,
            "offset": 0,
            "search": "",
            "sort": "artist",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_parser_accepts_all_local_commands(self) -> None:
        parser = mvp_bridge.build_parser()
        for command in (
            "local_roots", "local_root_add", "local_root_remove", "local_scan",
            "local_tracks", "local_track", "local_stats",
        ):
            parsed = parser.parse_args([command])
            self.assertEqual(parsed.command, command)

    def test_root_add_reads_path_from_environment_not_argv(self) -> None:
        service = Mock()
        service.add_root.return_value = {"root": {"path": r"C:\Музыка"}}
        with patch.object(mvp_bridge, "LocalLibraryService", return_value=service):
            with patch.dict(os.environ, {"MUSICARK_LOCAL_ROOT": r"C:\Музыка"}, clear=False):
                result = mvp_bridge._local_payload(self.args("local_root_add"), Path("."))
        service.add_root.assert_called_once_with(r"C:\Музыка")
        self.assertEqual(result["root"]["path"], r"C:\Музыка")

    def test_track_query_forwards_pagination_search_sort_and_root(self) -> None:
        service = Mock()
        service.tracks.return_value = {"count": 0, "items": []}
        args = self.args(
            "local_tracks",
            root_id=7,
            limit=250,
            offset=500,
            search="Linkin Park",
            sort="album",
        )
        with patch.object(mvp_bridge, "LocalLibraryService", return_value=service):
            result = mvp_bridge._local_payload(args, Path("."))
        service.tracks.assert_called_once_with(
            limit=250,
            offset=500,
            search="Linkin Park",
            sort="album",
            root_id=7,
        )
        self.assertEqual(result["count"], 0)

    def test_scan_all_and_scan_one_have_distinct_contracts(self) -> None:
        service = Mock()
        service.scan.side_effect = [{"added": 1}, {"added": 0}]
        with patch.object(mvp_bridge, "LocalLibraryService", return_value=service):
            all_result = mvp_bridge._local_payload(self.args("local_scan"), Path("."))
            one_result = mvp_bridge._local_payload(self.args("local_scan", root_id=3), Path("."))
        self.assertEqual(all_result["added"], 1)
        self.assertEqual(one_result["added"], 0)
        self.assertEqual(service.scan.call_args_list[0].args, (None,))
        self.assertEqual(service.scan.call_args_list[1].args, (3,))


if __name__ == "__main__":
    unittest.main()
