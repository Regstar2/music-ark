"""Offline tests for the unified official-desktop upload ground-truth PoC."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_ground_truth_poc.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_ground_truth_poc", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
poc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(poc)


class _FakeCdpClient:
    def __init__(self, url: str) -> None:
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class YandexUploadGroundTruthPocTests(unittest.TestCase):
    def test_combine_results_requires_unambiguous_readback(self) -> None:
        trace = {
            "format": "musicark-yandex-upload-cdp-runtime-report-v1",
            "events": [{"event": "request"}],
            "probe": {"rawCdpPersisted": False},
        }
        ground_truth = {
            "stage1": {"hosts": ["music.yandex.ru"]},
            "runtime": {"authorizationSources": ["account-oauth"]},
            "stage2": {"multipartPostObserved": True},
            "processing": {"requestObserved": True},
            "directHttpDecision": "account-oauth-profile-candidate",
        }
        assisted = {
            "mutation": {"initiatedByMusicArk": False, "singleFileOnly": True},
            "readBack": {"verified": True, "ambiguous": False, "verifiedTrackId": "ugc-1"},
        }
        result = poc.combine_results(trace_report=trace, ground_truth=ground_truth, assisted_payload=assisted)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["transportMode"], "official-desktop-assisted")
        self.assertEqual(result["readBack"]["verifiedTrackId"], "ugc-1")
        self.assertFalse(result["trace"]["rawCdpPersisted"])
        self.assertTrue(all(value is False for value in result["safety"].values()))

    def test_ambiguous_readback_is_not_verified(self) -> None:
        result = poc.combine_results(
            trace_report={"format": "musicark-yandex-upload-cdp-runtime-report-v1", "events": [], "probe": {}},
            ground_truth={},
            assisted_payload={"readBack": {"verified": False, "ambiguous": True}},
        )
        self.assertEqual(result["status"], "uploaded_unverified")

    def test_run_orchestrates_sanitized_trace_and_readback_offline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instrument = root / "instrument.js"
            instrument.write_text("(()=>{})();", encoding="utf-8")
            args = argparse.Namespace(
                base_dir=None,
                file=str(root / "owned.mp3"),
                playlist_kind="1055",
                confirm_owned_file=True,
                confirm_desktop_upload=True,
                port=9222,
                target_contains="Yandex",
                launch_exe=None,
                launch_wait=0.0,
                trace_duration=0.05,
                instrumentation_js=instrument,
                readback_attempts=1,
                readback_delay=0.0,
                trace_output=root / "trace.json",
                decision_output=root / "decision.json",
                output=root / "result.json",
            )
            Path(args.file).write_bytes(b"audio")
            target = {"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1", "type": "page", "url": "https://music.yandex.ru"}
            trace_report = {
                "format": "musicark-yandex-upload-cdp-runtime-report-v1",
                "events": [],
                "probe": {"rawCdpPersisted": False},
                "safety": {
                    "header_values_included": False,
                    "query_values_included": False,
                    "cookie_values_included": False,
                    "authorization_values_included": False,
                    "signed_urls_included": False,
                    "raw_response_bodies_included": False,
                    "raw_cdp_messages_included": False,
                },
            }
            decision = {
                "stage1": {"observed": True, "hosts": ["music.yandex.ru"]},
                "runtime": {"authorizationSources": ["account-oauth"]},
                "stage2": {"multipartPostObserved": True},
                "processing": {"requestObserved": True},
                "directHttpDecision": "account-oauth-profile-candidate",
            }
            assisted_payload = {
                "mutation": {"initiatedByMusicArk": False, "singleFileOnly": True},
                "readBack": {"verified": True, "ambiguous": False, "verifiedTrackId": "ugc-1"},
            }

            with patch.object(poc.cdp, "discover_targets", return_value=[target]), \
                 patch.object(poc.cdp, "select_target", return_value=target), \
                 patch.object(poc.cdp, "CdpClient", _FakeCdpClient), \
                 patch.object(poc.cdp, "collect_trace", return_value=[]), \
                 patch.object(poc.cdp, "build_report", return_value=trace_report), \
                 patch.object(poc.assisted, "run", return_value=(assisted_payload, 0)), \
                 patch.object(poc.analyzer, "analyze", return_value=decision):
                result, code = poc.run(args, prompt=lambda _: "")

            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "verified")
            self.assertTrue(args.trace_output.is_file())
            self.assertTrue(args.decision_output.is_file())
            self.assertTrue(args.output.is_file())

    def test_parser_does_not_enable_live_direct_http_or_secret_input(self) -> None:
        parser = poc.build_parser()
        option_strings = {option for action in parser._actions for option in action.option_strings}  # noqa: SLF001
        self.assertNotIn("--token", option_strings)
        self.assertNotIn("--oauth-token", option_strings)
        self.assertNotIn("--stage1-base-url", option_strings)


if __name__ == "__main__":
    unittest.main()
