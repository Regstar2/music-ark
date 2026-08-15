"""Bridge contract tests for MusicArk v0.6 coverage commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from musicark import mvp_bridge


class CoverageBridgeV06Tests(unittest.TestCase):
    def args(self, command: str, **overrides: object) -> argparse.Namespace:
        values = {
            "command": command,
            "provider_id": "yandex_music",
            "external_id": None,
            "local_file_id": None,
            "collection_id": "",
            "status": "",
            "user_action": "",
            "variant_status": "",
            "action": "",
            "limit": 100,
            "offset": 0,
            "search": "",
            "sort": "artist",
            "force": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_parser_accepts_all_coverage_commands(self) -> None:
        parser = mvp_bridge.build_parser()
        for command in (
            "coverage_summary",
            "coverage_tracks",
            "coverage_track",
            "coverage_collections",
            "coverage_set_action",
            "coverage_set_actions",
        ):
            parsed = parser.parse_args([command])
            self.assertEqual(parsed.command, command)

    def test_tracks_forwards_sql_filter_contract(self) -> None:
        service = Mock()
        service.tracks.return_value = {"count": 0, "items": []}
        args = self.args(
            "coverage_tracks",
            collection_id="playlist:501",
            status="missing",
            user_action="wanted",
            variant_status="",
            search="artist",
            sort="title",
            limit=50,
            offset=100,
        )
        with patch.object(
            mvp_bridge, "LibraryCoverageService", return_value=service
        ) as factory:
            result = mvp_bridge._coverage_payload(args, Path("."))
        factory.assert_called_once_with(
            base_dir=Path("."), provider_id="yandex_music"
        )
        service.tracks.assert_called_once_with(
            collection_id="playlist:501",
            status="missing",
            search="artist",
            sort="title",
            user_action="wanted",
            variant_status="",
            limit=50,
            offset=100,
        )
        self.assertEqual(result["count"], 0)

    def test_bulk_ids_use_structured_environment_payload(self) -> None:
        service = Mock()
        service.set_actions.return_value = {"updated": 2, "action": "wanted"}
        args = self.args("coverage_set_actions", action="wanted")
        with patch.dict(
            os.environ,
            {"MUSICARK_COVERAGE_BULK": json.dumps(["10", "20"])},
            clear=False,
        ):
            with patch.object(
                mvp_bridge, "LibraryCoverageService", return_value=service
            ):
                result = mvp_bridge._coverage_payload(args, Path("."))
        service.set_actions.assert_called_once_with(["10", "20"], "wanted")
        self.assertEqual(result["updated"], 2)

    def test_bulk_rejects_non_array_payload(self) -> None:
        args = self.args("coverage_set_actions", action="ignored")
        with patch.dict(
            os.environ, {"MUSICARK_COVERAGE_BULK": '{"id":"10"}'}, clear=False
        ):
            with patch.object(
                mvp_bridge, "LibraryCoverageService", return_value=Mock()
            ):
                with self.assertRaises(mvp_bridge.BridgeRequestError):
                    mvp_bridge._coverage_payload(args, Path("."))

    def test_single_action_requires_external_id_and_action(self) -> None:
        with patch.object(
            mvp_bridge, "LibraryCoverageService", return_value=Mock()
        ):
            with self.assertRaises(mvp_bridge.BridgeRequestError):
                mvp_bridge._coverage_payload(
                    self.args("coverage_set_action", action="wanted"),
                    Path("."),
                )
            with self.assertRaises(mvp_bridge.BridgeRequestError):
                mvp_bridge._coverage_payload(
                    self.args("coverage_set_action", external_id="10"),
                    Path("."),
                )


if __name__ == "__main__":
    unittest.main()
