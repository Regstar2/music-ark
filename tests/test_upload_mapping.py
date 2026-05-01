"""Tests upload replacement mapping JSON (v0.11)."""

from __future__ import annotations

import unittest

from musicark.providers.yandex_upload_mapping import build_upload_replacement_mapping


class UploadMappingTests(unittest.TestCase):
    def test_build_mapping_known_keys(self) -> None:
        m = build_upload_replacement_mapping(
            original_external_id="123456",
            local_file_id=7,
            uploaded_external_id="user:abc",
            upload_status="ok",
            detail="",
        )
        self.assertEqual(m["original_yandex_external_id"], "123456")
        self.assertEqual(m["local_file_id"], 7)
        self.assertEqual(m["uploaded_yandex_external_id"], "user:abc")
        self.assertTrue(m["replacement_ready"])

    def test_replacement_pending_without_uploaded_id(self) -> None:
        m = build_upload_replacement_mapping(
            original_external_id="1",
            local_file_id=2,
            uploaded_external_id=None,
            upload_status="not_supported",
            detail="no api",
        )
        self.assertFalse(m["replacement_ready"])
        self.assertEqual(m["upload_status"], "not_supported")


if __name__ == "__main__":
    unittest.main()
