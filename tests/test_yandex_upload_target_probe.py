"""Tests for the targeted, offline Yandex upload ASAR probe."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "yandex_upload_target_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_target_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


def _pickle_uint32(value: int) -> bytes:
    return struct.pack("<II", 4, value)


def _pickle_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    payload = struct.pack("<i", len(encoded)) + encoded
    payload += b"\x00" * ((4 - (len(encoded) % 4)) % 4)
    return struct.pack("<I", len(payload)) + payload


def _build_asar(member_name: str, content: bytes) -> tuple[bytes, int]:
    header = {
        "files": {
            member_name: {
                "size": len(content),
                "offset": "0",
            }
        }
    }
    header_pickle = _pickle_string(json.dumps(header, separators=(",", ":")))
    data_start = 8 + len(header_pickle)
    return _pickle_uint32(len(header_pickle)) + header_pickle + content, data_start


class YandexUploadTargetProbeTests(unittest.TestCase):
    def test_maps_raw_offset_to_asar_member(self) -> None:
        content = b'const marker="getUploadUrl"; const body = new FormData(); body.append("file", f);'
        archive, data_start = _build_asar("app/chunk.js", content)
        target = data_start + content.index(b"getUploadUrl")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.asar"
            path.write_bytes(archive)
            actual_data_start, mappings = probe.locate_members(path, [target])

        self.assertEqual(actual_data_start, data_start)
        self.assertEqual(mappings[0]["members"][0]["path"], "app/chunk.js")
        self.assertEqual(
            mappings[0]["members"][0]["relative_offset"],
            content.index(b"getUploadUrl"),
        )

    def test_report_keeps_protocol_structure_and_omits_secret_source_values(self) -> None:
        secret = "very-private-session-cookie-value"
        content = (
            f'const auth="Authorization: Bearer {secret}";'
            'async function getUploadUrl() {'
            'return this.httpClient.post("/ugc/upload/url?sign=private-value", {playlistId: x});'
            '}'
            'async function uploadFile(uploadUrl, file) {'
            'const body = new FormData(); body.append("file", file);'
            'return this.httpClient.post(uploadUrl, {body});'
            '}'
        ).encode("utf-8")
        archive, data_start = _build_asar("app/upload-client.js", content)
        target = data_start + content.index(b"uploadFile")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.asar"
            path.write_bytes(archive)
            report = probe.build_report(path, [target], radius=4096)

        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("Authorization", encoded)
        self.assertNotIn("private-value", encoded)
        self.assertNotIn("sign=", encoded)

        member = report["targets"][0]["members"][0]
        self.assertEqual(member["path"], "app/upload-client.js")
        structure = member["member_structure"]
        self.assertIn("file", structure["form_fields"])
        self.assertIn("getUploadUrl", structure["named_calls"])
        self.assertIn("uploadFile", structure["named_calls"])
        self.assertIn(
            {"method": "POST", "target_kind": "identifier", "target": "uploadUrl"},
            structure["http_calls"],
        )

    def test_rejects_non_asar_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not.asar"
            path.write_bytes(b"not-an-asar")
            with self.assertRaises(probe.AsarFormatError):
                probe.read_asar_header(path)


if __name__ == "__main__":
    unittest.main()
