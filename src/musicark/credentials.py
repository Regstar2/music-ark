"""Secure credential storage for MusicArk desktop sessions."""

from __future__ import annotations

from typing import Protocol

from musicark.core.errors import MusicArkError


class CredentialStoreError(MusicArkError):
    """Raised when the operating-system credential store cannot be used."""


class CredentialStore(Protocol):
    def get_token(self) -> str | None: ...

    def set_token(self, token: str) -> None: ...

    def delete_token(self) -> None: ...


class SystemCredentialStore:
    """Store the Yandex token in the OS keyring (Windows Credential Locker on Windows)."""

    SERVICE_NAME = "MusicArk"
    USERNAME = "yandex_music_token"

    @staticmethod
    def _keyring_module():  # type: ignore[no-untyped-def]
        try:
            import keyring  # type: ignore
        except ImportError as exc:
            raise CredentialStoreError(
                "Python keyring dependency is missing. Reinstall MusicArk dependencies."
            ) from exc

        try:
            backend = keyring.get_keyring()
            priority = float(getattr(backend, "priority", 0))
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to initialize the system credential store.") from exc
        if priority <= 0:
            raise CredentialStoreError("No usable secure system credential backend is available.")
        return keyring

    def get_token(self) -> str | None:
        keyring = self._keyring_module()
        try:
            token = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to read the saved Yandex token.") from exc
        token = token.strip() if token else ""
        return token or None

    def set_token(self, token: str) -> None:
        clean = token.strip()
        if not clean:
            raise CredentialStoreError("Refusing to save an empty Yandex token.")
        keyring = self._keyring_module()
        try:
            keyring.set_password(self.SERVICE_NAME, self.USERNAME, clean)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to save the Yandex token securely.") from exc

    def delete_token(self) -> None:
        keyring = self._keyring_module()
        try:
            existing = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
            if existing is None:
                return
            keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreError("Failed to delete the saved Yandex token.") from exc
