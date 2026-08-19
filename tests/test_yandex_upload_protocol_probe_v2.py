"""Regression tests for balanced static Yandex upload protocol scanning."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "yandex_upload_protocol_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_protocol_probe_v2", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadProtocolProbeV2Tests(unittest.TestCase):
    def test_noisy_upload_keyword_does_not_starve_other_keywords(self) -> None:
        source = (
            (" upload " * 100)
            + ' const playlistUuid="private-value"; '
            + ' const data=new FormData(); data.append("file", blob); '
            + ' client.httpClient.post("/ugc/tracks/upload", data); '
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.asar"
            path.write_bytes(source)
            report = probe.scan_binary(
                path,
                keywords=("upload", "playlistuuid", "formdata", "httpclient.post"),
                max_hits=20,
                max_hits_per_keyword=2,
                context_radius=512,
            )

        self.assertEqual(report["format"], "musicark-yandex-upload-protocol-report-v2")
        self.assertGreater(report["keyword_counts"]["playlistuuid"], 0)
        self.assertGreater(report["keyword_counts"]["formdata"], 0)
        self.assertGreater(report["keyword_counts"]["httpclient.post"], 0)
        self.assertIn("upload", report["truncated_keywords"])

        encoded = json.dumps(report, ensure_ascii=False)
        self.assertIn("/ugc/tracks/upload", encoded)
        self.assertIn("file", encoded)
        self.assertNotIn("private-value", encoded)
        self.assertNotIn("const playlistUuid", encoded)

    def test_structural_hints_include_audio_shape_only(self) -> None:
        source = (
            'const audioUpload=new FormData(); '
            'audioUpload.append("track", privateBlob); '
            'client.httpClient.post("/tracks/upload", audioUpload); '
            'const mime="audio/mpeg"; const ext=".mp3";'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.asar"
            path.write_bytes(source)
            report = probe.scan_binary(
                path,
                keywords=("formdata",),
                max_hits=5,
                max_hits_per_keyword=5,
                context_radius=512,
            )

        hit = report["hits"][0]
        self.assertIn("POST", hit["http_methods"])
        self.assertIn("track", hit["form_fields"])
        self.assertIn("audio/mpeg", hit["mime_types"])
        self.assertIn(".mp3", hit["audio_extensions"])
        self.assertIn("audioUpload", hit["related_identifiers"])
        self.assertNotIn("privateBlob", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
