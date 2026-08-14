"""Application service for MusicArk v0.2 persistent liked-track library."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from musicark.core.config import load_config
from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.providers.yandex_music_provider import (
    YandexMusicProvider,
    YandexTokenMissingError,
)
from musicark.storage.liked_cache import LikedCacheRepository, LikedCacheSnapshot


ProviderFactory = Callable[[str], YandexMusicProvider]


class PersistentLibraryService:
    def __init__(
        self,
        base_dir: Path | None = None,
        credential_store: CredentialStore | None = None,
        cache: LikedCacheRepository | None = None,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._credentials = credential_store or SystemCredentialStore()
        self._cache = cache or LikedCacheRepository(self._resolve_database_path())
        self._provider_factory = provider_factory

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def _provider(self, token: str) -> YandexMusicProvider:
        if self._provider_factory is not None:
            return self._provider_factory(token)
        return YandexMusicProvider(base_dir=self._base_dir, token=token)

    @staticmethod
    def _library_payload(
        snapshot: LikedCacheSnapshot,
        *,
        source: str,
        diff: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        return {
            "source": source,
            "count": snapshot.count,
            "lastUpdated": snapshot.refreshed_at,
            "tracks": snapshot.tracks,
            "diff": diff or {"added": 0, "removed": 0, "unchanged": snapshot.count},
        }

    def bootstrap(self) -> dict[str, Any]:
        token = self._credentials.get_token()
        snapshot = self._cache.load()
        return {
            "session": {
                "hasStoredToken": token is not None,
                "account": snapshot.account if token else {},
            },
            "library": self._library_payload(snapshot, source="cache"),
        }

    def login(self, token: str) -> dict[str, Any]:
        clean = token.strip()
        if not clean:
            raise YandexTokenMissingError("Yandex token is empty.")

        provider = self._provider(clean)
        account = provider.auth_check()
        tracks = provider.list_tracks()

        self._credentials.set_token(clean)
        try:
            diff = self._cache.replace(account, tracks)
        except Exception:
            # Avoid a half-signed-in state if persistence fails after secure save.
            self._credentials.delete_token()
            raise

        snapshot = self._cache.load()
        return {
            "session": {"hasStoredToken": True, "account": account},
            "library": self._library_payload(snapshot, source="network", diff=diff),
        }

    def refresh(self) -> dict[str, Any]:
        token = self._credentials.get_token()
        if not token:
            raise YandexTokenMissingError("No saved Yandex token is available.")

        provider = self._provider(token)
        account = provider.auth_check()
        tracks = provider.list_tracks()
        diff = self._cache.replace(account, tracks)
        snapshot = self._cache.load()
        return {
            "session": {"hasStoredToken": True, "account": account},
            "library": self._library_payload(snapshot, source="network", diff=diff),
        }

    def cached(self) -> dict[str, Any]:
        snapshot = self._cache.load()
        return {
            "session": {
                "hasStoredToken": self._credentials.get_token() is not None,
                "account": snapshot.account,
            },
            "library": self._library_payload(snapshot, source="cache"),
        }

    def logout(self) -> dict[str, Any]:
        self._credentials.delete_token()
        self._cache.clear()
        return {
            "session": {"hasStoredToken": False, "account": {}},
            "library": {
                "source": "none",
                "count": 0,
                "lastUpdated": None,
                "tracks": [],
                "diff": {"added": 0, "removed": 0, "unchanged": 0},
            },
        }
