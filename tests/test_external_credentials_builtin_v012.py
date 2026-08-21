from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from musicark.external_metadata.credentials import ExternalCredentialStore


class _NoKeyringExternalCredentialStore(ExternalCredentialStore):
    def _keyring_value(self, name: str) -> str | None:  # type: ignore[override]
        return None


class ExternalCredentialBuiltinV012Tests(unittest.TestCase):
    def test_acoustid_is_zero_config_application_credential(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MUSICARK_ACOUSTID_CLIENT_KEY", None)
            value, origin = _NoKeyringExternalCredentialStore().get_with_origin("acoustid_key")
        self.assertTrue(value)
        self.assertEqual(origin, "application")

    def test_environment_can_override_bundled_acoustid_application_key(self) -> None:
        with patch.dict(os.environ, {"MUSICARK_ACOUSTID_CLIENT_KEY": "dev-override"}, clear=False):
            value, origin = _NoKeyringExternalCredentialStore().get_with_origin("acoustid_key")
        self.assertEqual(value, "dev-override")
        self.assertEqual(origin, "application")

    def test_acoustid_user_submission_key_is_not_supported(self) -> None:
        self.assertNotIn("acoustid_user_key", ExternalCredentialStore._ALLOWED)


if __name__ == "__main__":
    unittest.main()
