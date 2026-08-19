"""Offline tests for passportCredentials.host structural provenance."""

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

_TOOL = _TOOLS / "yandex_upload_passport_host_source_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_passport_host_source_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPassportHostSourceProbeTests(unittest.TestCase):
    def test_object_host_maps_stable_module_source(self) -> None:
        body = 'var a=n(55);const cfg={passportCredentials:{host:a.host,common:{oauth:"DO_NOT_EMIT"}}};'
        records = probe._schema_object_records("1", body)  # noqa: SLF001
        self.assertEqual(records[0]["host"]["sourceRefs"], [{"source_module_id": "55", "export_key": "host"}])
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertNotIn("DO_NOT_EMIT", encoded)

    def test_safe_yandex_template_is_preserved(self) -> None:
        body = 'const cfg={passportCredentials:{host:"https://passport.yandex.{tld}"}};'
        records = probe._schema_object_records("1", body)  # noqa: SLF001
        self.assertEqual(records[0]["host"]["safeYandexTemplates"], ["https://passport.yandex.{tld}"])

    def test_sensitive_module_member_is_redacted(self) -> None:
        body = 'var a=n(55);const cfg={passportCredentials:{host:a.secretToken}};'
        encoded = json.dumps(probe._schema_object_records("1", body), ensure_ascii=False)  # noqa: SLF001
        self.assertNotIn("secretToken", encoded)
        self.assertIn("<redacted-sensitive-member>", encoded)

    def test_semantic_config_host_path_is_allowed(self) -> None:
        body = 'const cfg={passportCredentials:{host:this.clientSafeConfig.passportCredentials.host}};'
        records = probe._schema_object_records("1", body)  # noqa: SLF001
        self.assertIn(
            ["clientSafeConfig", "passportCredentials", "host"],
            records[0]["host"]["semanticPaths"],
        )


if __name__ == "__main__":
    unittest.main()
