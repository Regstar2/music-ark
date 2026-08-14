"""Bridge contract tests for MusicArk v0.5.1 variant commands."""

from __future__ import annotations

import argparse
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from musicark import mvp_bridge


class VariantBridgeV051Tests(unittest.TestCase):
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
            "force": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_parser_accepts_all_variant_commands(self) -> None:
        parser = mvp_bridge.build_parser()
        for command in (
            "variant_capabilities",
            "variant_summary",
            "variant_run",
            "variant_run_all_available",
            "variant_result",
            "variant_results",
        ):
            parsed = parser.parse_args([command])
            self.assertEqual(parsed.command, command)

    def test_results_forwards_pagination_and_status(self) -> None:
        service = Mock()
        service.results.return_value = {"count": 0, "items": []}
        args = self.args(
            "variant_results",
            limit=50,
            offset=100,
            status="altered",
        )
        with patch.object(mvp_bridge, "VariantDetectionService", return_value=service) as factory:
            result = mvp_bridge._variant_payload(args, Path("."))
        factory.assert_called_once_with(base_dir=Path("."), provider_id="yandex_music")
        service.results.assert_called_once_with(limit=50, offset=100, status="altered")
        self.assertEqual(result["count"], 0)

    def test_single_run_requires_identity_and_forwards_force(self) -> None:
        service = Mock()
        service.run.return_value = {"result": {"variantStatus": "same"}}
        with patch.object(mvp_bridge, "VariantDetectionService", return_value=service):
            result = mvp_bridge._variant_payload(
                self.args("variant_run", external_id="69046542", force=True),
                Path("."),
            )
        service.run.assert_called_once_with("69046542", force=True)
        self.assertEqual(result["result"]["variantStatus"], "same")

    def test_missing_external_id_is_rejected_for_single_track_commands(self) -> None:
        for command in ("variant_run", "variant_result"):
            with self.subTest(command=command):
                with patch.object(mvp_bridge, "VariantDetectionService", return_value=Mock()):
                    with self.assertRaises(mvp_bridge.BridgeRequestError):
                        mvp_bridge._variant_payload(self.args(command), Path("."))

    def test_batch_and_capabilities_have_separate_service_calls(self) -> None:
        service = Mock()
        service.capabilities.return_value = {"ffmpegAvailable": False}
        service.run_all_available.return_value = {"processed": 0}
        with patch.object(mvp_bridge, "VariantDetectionService", return_value=service):
            capabilities = mvp_bridge._variant_payload(
                self.args("variant_capabilities"), Path(".")
            )
            batch = mvp_bridge._variant_payload(
                self.args("variant_run_all_available"), Path(".")
            )
        self.assertFalse(capabilities["ffmpegAvailable"])
        self.assertEqual(batch["processed"], 0)


if __name__ == "__main__":
    unittest.main()
