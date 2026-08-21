"""Secure credentials used by optional external metadata integrations."""

from __future__ import annotations

import os
from typing import Any

from musicark.credentials import CredentialStoreError, SystemCredentialStore


class ExternalCredentialStore:
    """Keep provider/proxy secrets in the OS keyring, never in preference JSON.

    Provider application keys are not user-account credentials. Release builds
    may supply them through the process environment/build configuration, while
    local developers can override them through the OS keyring. TheAudioDB's
    documented public free-tier key is a non-secret built-in fallback for the
    development/free integration and must be reviewed again before app-store or
    commercial distribution.
    """

    SERVICE_NAME = "MusicArk.ExternalMetadata"
    _ALLOWED = {"acoustid_key", "discogs_token", "theaudiodb_key", "lastfm_key", "lastfm_secret", "proxy_password"}
    _ENVIRONMENT = {
        "acoustid_key": "MUSICARK_ACOUSTID_CLIENT_KEY",
        "discogs_token": "MUSICARK_DISCOGS_TOKEN",
        "theaudiodb_key": "MUSICARK_THEAUDIODB_KEY",
        "lastfm_key": "MUSICARK_LASTFM_API_KEY",
        "lastfm_secret": "MUSICARK_LASTFM_API_SECRET",
    }
    _BUILTIN = {
        # Public free V1 key documented by TheAudioDB. This is intentionally not
        # treated as a secret. Publishing/commercial terms are documented in
        # docs/architecture/external-metadata-sources.md and must be rechecked.
        "theaudiodb_key": "123",
    }

    @staticmethod
    def _keyring():
        return SystemCredentialStore._keyring_module()  # noqa: SLF001 - shared validated OS-keyring boundary.

    def _keyring_value(self, name: str) -> str | None:
        try:
            value = self._keyring().get_password(self.SERVICE_NAME, name)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to read an external MusicArk credential.") from exc
        value = value.strip() if value else ""
        return value or None

    def get_with_origin(self, name: str) -> tuple[str | None, str]:
        if name not in self._ALLOWED:
            raise CredentialStoreError(f"Unsupported external credential '{name}'.")

        keyring_value = self._keyring_value(name)
        if keyring_value:
            return keyring_value, "keyring"

        env_name = self._ENVIRONMENT.get(name)
        if env_name:
            env_value = os.getenv(env_name, "").strip()
            if env_value:
                return env_value, "application"

        builtin = self._BUILTIN.get(name)
        if builtin:
            return builtin, "builtin_free"
        return None, "missing"

    def get(self, name: str) -> str | None:
        return self.get_with_origin(name)[0]

    def public_status(self) -> dict[str, Any]:
        providers = {
            "acoustid": "acoustid_key",
            "discogs": "discogs_token",
            "theaudiodb": "theaudiodb_key",
            "lastfm": "lastfm_key",
        }
        result: dict[str, Any] = {}
        for provider, credential_name in providers.items():
            value, origin = self.get_with_origin(credential_name)
            result[provider] = {
                "configured": bool(value),
                "origin": origin,
                # These are application/developer integration credentials. An
                # ordinary MusicArk end user should not be required to obtain
                # them for the default MusicBrainz + CAA workflow.
                "advanced": provider in {"acoustid", "discogs", "lastfm"},
            }
        return result

    def set(self, name: str, value: str | None) -> None:
        if name not in self._ALLOWED:
            raise CredentialStoreError(f"Unsupported external credential '{name}'.")
        clean = str(value or "").strip()
        keyring = self._keyring()
        try:
            existing = keyring.get_password(self.SERVICE_NAME, name)
            if not clean:
                if existing is not None:
                    keyring.delete_password(self.SERVICE_NAME, name)
                return
            keyring.set_password(self.SERVICE_NAME, name, clean)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to update an external MusicArk credential.") from exc
