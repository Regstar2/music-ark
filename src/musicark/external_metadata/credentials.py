"""Secure credentials used by optional external metadata integrations."""

from __future__ import annotations

from musicark.credentials import CredentialStoreError, SystemCredentialStore


class ExternalCredentialStore:
    """Keep provider/proxy secrets in the OS keyring, never in preference JSON."""

    SERVICE_NAME = "MusicArk.ExternalMetadata"
    _ALLOWED = {"acoustid_key", "discogs_token", "theaudiodb_key", "lastfm_key", "lastfm_secret", "proxy_password"}

    @staticmethod
    def _keyring():
        return SystemCredentialStore._keyring_module()  # noqa: SLF001 - shared validated OS-keyring boundary.

    def get(self, name: str) -> str | None:
        if name not in self._ALLOWED:
            raise CredentialStoreError(f"Unsupported external credential '{name}'.")
        try:
            value = self._keyring().get_password(self.SERVICE_NAME, name)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to read an external MusicArk credential.") from exc
        value = value.strip() if value else ""
        return value or None

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
