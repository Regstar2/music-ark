"""Offline tests for the passportCredentials stage-one host probe."""

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

_TOOL = _TOOLS / "yandex_upload_passport_credentials_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_passport_credentials_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadPassportCredentialsProbeTests(unittest.TestCase):
    def test_safe_public_yandex_host_is_preserved_without_query(self) -> None:
        self.assertEqual(
            probe._safe_url_or_template("https://passport.yandex.ru/api"),  # noqa: SLF001
            "https://passport.yandex.ru/api",
        )
        self.assertIsNone(probe._safe_url_or_template("https://passport.yandex.ru/api?token=SECRET"))  # noqa: SLF001

    def test_tld_template_is_allowed(self) -> None:
        self.assertEqual(
            probe._safe_url_or_template("https://passport.yandex.{tld}"),  # noqa: SLF001
            "https://passport.yandex.{tld}",
        )

    def test_schema_object_emits_only_allowlisted_keys_and_safe_hosts(self) -> None:
        text = (
            'const cfg={passportCredentials:{host:"https://passport.yandex.{tld}",'
            'common:{oauth:"DO_NOT_EMIT"},privateValue:"SUPER_SECRET"}};'
        )
        records = probe._schema_objects(text)  # noqa: SLF001
        encoded = json.dumps(records, ensure_ascii=False)
        self.assertIn("https://passport.yandex.{tld}", encoded)
        self.assertIn("host", encoded)
        self.assertIn("oauth", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)
        self.assertNotIn("SUPER_SECRET", encoded)
        self.assertNotIn("privateValue", encoded)

    def test_non_yandex_literal_is_not_emitted(self) -> None:
        text = 'const cfg={passportCredentials:{host:"https://example.com",x:"DO_NOT_EMIT"}};'
        encoded = json.dumps(probe._schema_objects(text), ensure_ascii=False)  # noqa: SLF001
        self.assertNotIn("example.com", encoded)
        self.assertNotIn("DO_NOT_EMIT", encoded)


if __name__ == "__main__":
    unittest.main()
