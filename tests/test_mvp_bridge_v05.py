"""Bridge contract tests for MusicArk v0.5 matching commands."""

from __future__ import annotations

import argparse
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from musicark import mvp_bridge


class MatchingBridgeV05Tests(unittest.TestCase):
    def args(self, command: str, **overrides: object) -> argparse.Namespace:
        values = {
            "command": command,
            "provider_id": "yandex_music",
            "external_id": None,
            "local_file_id": None,
            "status": "",
            "limit": 100,
            "offset": 0,
            "search": "",
            "sort": "confidence",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_parser_accepts_all_matching_commands(self) -> None:
        parser = mvp_bridge.build_parser()
        for command in (
            "matching_summary", "matching_run", "matching_results",
            "matching_result", "matching_accept", "matching_reject",
        ):
            parsed = parser.parse_args([command])
            self.assertEqual(parsed.command, command)

    def test_results_forwards_pagination_status_search_and_sort(self) -> None:
        service = Mock()
        service.results.return_value = {"count": 0, "items": []}
        args = self.args(
            "matching_results",
            limit=50,
            offset=100,
            status="conflict",
            search="Linkin Park",
            sort="title",
        )
        with patch.object(mvp_bridge, "MatchingService", return_value=service) as factory:
            result = mvp_bridge._matching_payload(args, Path("."))
        factory.assert_called_once_with(base_dir=Path("."), provider_id="yandex_music")
        service.results.assert_called_once_with(
            limit=50,
            offset=100,
            status="conflict",
            search="Linkin Park",
            sort="title",
        )
        self.assertEqual(result["count"], 0)

    def test_accept_and_reject_require_structured_ids(self) -> None:
        service = Mock()
        service.accept.return_value = {"result": {"status": "matched"}}
        service.reject.return_value = {"result": {"status": "unmatched"}}
        with patch.object(mvp_bridge, "MatchingService", return_value=service):
            accepted = mvp_bridge._matching_payload(
                self.args("matching_accept", external_id="123", local_file_id=7),
                Path("."),
            )
            rejected = mvp_bridge._matching_payload(
                self.args("matching_reject", external_id="124", local_file_id=8),
                Path("."),
            )
        service.accept.assert_called_once_with("123", 7)
        service.reject.assert_called_once_with("124", 8)
        self.assertEqual(accepted["result"]["status"], "matched")
        self.assertEqual(rejected["result"]["status"], "unmatched")

    def test_missing_matching_identity_is_rejected(self) -> None:
        with patch.object(mvp_bridge, "MatchingService", return_value=Mock()):
            with self.assertRaises(mvp_bridge.BridgeRequestError):
                mvp_bridge._matching_payload(self.args("matching_result"), Path("."))


if __name__ == "__main__":
    unittest.main()
