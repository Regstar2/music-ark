"""Application orchestration for the v0.3 Yandex Library desktop experience."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from musicark.core.config import load_config
from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.download.models import DownloadTask
from musicark.download.provider import YandexMusicDownloadProvider
from musicark.matching.scope import MatchingScopeState
from musicark.providers.yandex_music_provider import (
    YandexMusicProvider,
    YandexTokenMissingError,
)
from musicark.storage.liked_cache import LikedCacheRepository, LikedCacheSnapshot
from musicark.storage.playlist_cache import PlaylistCacheRepository, PlaylistCacheSnapshot

ProviderFactory = Callable[[str], YandexMusicProvider]


class YandexLibraryService:
    """Coordinate secure session, provider access, cache-first collections, and playback cache."""

    def __init__(
        self,
        base_dir: Path | None = None,
        credential_store: CredentialStore | None = None,
        liked_cache: LikedCacheRepository | None = None,
        playlist_cache: PlaylistCacheRepository | None = None,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._credentials = credential_store or SystemCredentialStore()
        database_path = self._resolve_database_path()
        self._database_path = database_path
        self._liked_cache = liked_cache or LikedCacheRepository(database_path)
        self._playlist_cache = playlist_cache or PlaylistCacheRepository(database_path)
        self._matching_scope = MatchingScopeState(database_path)
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

    def _saved_token(self) -> str:
        token = self._credentials.get_token()
        if not token:
            raise YandexTokenMissingError("No saved Yandex token is available.")
        return token

    @staticmethod
    def _liked_payload(
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

    @staticmethod
    def _playlist_index_payload(
        items: list[dict[str, Any]],
        *,
        source: str,
        diff: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        updates = [str(item["lastUpdated"]) for item in items if item.get("lastUpdated")]
        return {
            "source": source,
            "count": len(items),
            "lastUpdated": max(updates) if updates else None,
            "items": items,
            "diff": diff or {"added": 0, "removed": 0, "unchanged": len(items)},
        }

    @staticmethod
    def _playlist_collection_payload(
        snapshot: PlaylistCacheSnapshot,
        *,
        source: str,
        diff: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        last_updated = snapshot.content_refreshed_at or snapshot.refreshed_at
        return {
            "source": source,
            "count": snapshot.count,
            "lastUpdated": last_updated,
            "tracks": snapshot.tracks,
            "diff": diff or {"added": 0, "removed": 0, "unchanged": snapshot.count},
        }

    @staticmethod
    def _session(has_token: bool, account: dict[str, Any]) -> dict[str, Any]:
        return {"hasStoredToken": has_token, "account": account if has_token else {}}

    def _library_state(
        self,
        *,
        has_token: bool,
        account: dict[str, Any],
        liked: LikedCacheSnapshot,
        liked_source: str,
        playlists: list[dict[str, Any]],
        playlists_source: str,
        liked_diff: dict[str, int] | None = None,
        playlists_diff: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        liked_payload = self._liked_payload(liked, source=liked_source, diff=liked_diff)
        return {
            "session": self._session(has_token, account),
            "liked": liked_payload,
            "library": liked_payload,
            "playlists": self._playlist_index_payload(
                playlists,
                source=playlists_source,
                diff=playlists_diff,
            ),
        }

    def bootstrap(self) -> dict[str, Any]:
        token = self._credentials.get_token()
        liked = self._liked_cache.load()
        playlists = self._playlist_cache.list_metadata()
        if token:
            self._matching_scope.ensure_default()
        return self._library_state(
            has_token=token is not None,
            account=liked.account,
            liked=liked,
            liked_source="cache" if token else "none",
            playlists=playlists,
            playlists_source="cache" if token else "none",
        )

    def login(self, token: str) -> dict[str, Any]:
        clean = token.strip()
        if not clean:
            raise YandexTokenMissingError("Yandex token is empty.")

        provider = self._provider(clean)
        account = provider.auth_check()
        tracks = provider.list_tracks()
        playlists = provider.list_playlist_metadata()

        self._credentials.set_token(clean)
        try:
            liked_diff = self._liked_cache.replace(account, tracks)
            playlists_diff = self._playlist_cache.replace_index(playlists)
            self._matching_scope.set_liked()
        except Exception:
            self._credentials.delete_token()
            raise

        return self._library_state(
            has_token=True,
            account=account,
            liked=self._liked_cache.load(),
            liked_source="network",
            playlists=self._playlist_cache.list_metadata(),
            playlists_source="network",
            liked_diff=liked_diff,
            playlists_diff=playlists_diff,
        )

    def liked_refresh(self) -> dict[str, Any]:
        token = self._saved_token()
        provider = self._provider(token)
        account = provider.auth_check()
        tracks = provider.list_tracks()
        diff = self._liked_cache.replace(account, tracks)
        self._matching_scope.set_liked()
        return self._library_state(
            has_token=True,
            account=account,
            liked=self._liked_cache.load(),
            liked_source="network",
            playlists=self._playlist_cache.list_metadata(),
            playlists_source="cache",
            liked_diff=diff,
        )

    def refresh(self) -> dict[str, Any]:
        """Backward-compatible v0.2 alias for refreshing Liked."""
        return self.liked_refresh()

    def playlists(self) -> dict[str, Any]:
        liked = self._liked_cache.load()
        token = self._credentials.get_token()
        return self._library_state(
            has_token=token is not None,
            account=liked.account,
            liked=liked,
            liked_source="cache" if token else "none",
            playlists=self._playlist_cache.list_metadata(),
            playlists_source="cache" if token else "none",
        )

    def playlist(self, external_id: str) -> dict[str, Any]:
        snapshot = self._playlist_cache.load(external_id)
        liked = self._liked_cache.load()
        token = self._credentials.get_token()
        # A stale/deleted cached playlist can still be queried by legacy callers; only
        # an active playlist is allowed to become the current Matching scope.
        if snapshot.metadata:
            self._matching_scope.set_playlist(external_id)
        return {
            "session": self._session(token is not None, liked.account),
            "playlist": snapshot.metadata,
            "collection": self._playlist_collection_payload(snapshot, source="cache"),
        }

    def playlist_refresh(self, external_id: str) -> dict[str, Any]:
        token = self._saved_token()
        provider = self._provider(token)
        playlist, tracks = provider.get_playlist(external_id)
        diff = self._playlist_cache.replace_playlist(playlist, tracks)
        snapshot = self._playlist_cache.load(external_id)
        liked = self._liked_cache.load()
        self._matching_scope.set_playlist(external_id)
        return {
            "session": self._session(True, liked.account),
            "playlist": snapshot.metadata,
            "collection": self._playlist_collection_payload(
                snapshot,
                source="network",
                diff=diff,
            ),
        }

    def library_refresh(self) -> dict[str, Any]:
        """Refresh account, Liked, and playlist index without eagerly loading every playlist."""
        token = self._saved_token()
        provider = self._provider(token)
        account = provider.auth_check()
        tracks = provider.list_tracks()
        playlists = provider.list_playlist_metadata()

        liked_diff = self._liked_cache.replace(account, tracks)
        playlists_diff = self._playlist_cache.replace_index(playlists)
        self._matching_scope.ensure_default()
        return self._library_state(
            has_token=True,
            account=account,
            liked=self._liked_cache.load(),
            liked_source="network",
            playlists=self._playlist_cache.list_metadata(),
            playlists_source="network",
            liked_diff=liked_diff,
            playlists_diff=playlists_diff,
        )

    def playback_prepare(self, external_id: str) -> dict[str, Any]:
        """Acquire an authorized Yandex track into MusicArk's private playback cache.

        Flutter receives only the resulting local path. Provider download URLs and
        credentials stay inside the backend process, and the cache file is not added
        to Local Library or Matching.
        """
        identity = str(external_id).strip()
        if not identity.isdigit():
            raise ValueError("Yandex Track ID must be numeric.")
        token = self._saved_token()
        app_root = self._base_dir if self._base_dir is not None else self._database_path.parent.parent
        playback_root = app_root / ".musicark" / "playback" / "yandex"
        task = DownloadTask(
            task_type="yandex_playback",
            source_id=identity,
            provider_id="yandex_music_download",
            target_folder=str(playback_root),
            raw_payload={
                "track_id": identity,
                "quality": "best",
                "target_filename": f"yandex_{identity}.mp3",
            },
        )
        local_audio = YandexMusicDownloadProvider(
            base_dir=self._base_dir,
            token=token,
        ).execute(task)
        return {
            "providerId": "yandex_music",
            "externalId": identity,
            "path": local_audio.path,
            "cached": True,
        }

    def cached(self) -> dict[str, Any]:
        return self.bootstrap()

    def logout(self) -> dict[str, Any]:
        self._credentials.delete_token()
        self._liked_cache.clear()
        self._playlist_cache.clear()
        self._matching_scope.clear()
        liked = self._liked_cache.load()
        return self._library_state(
            has_token=False,
            account={},
            liked=liked,
            liked_source="none",
            playlists=[],
            playlists_source="none",
        )
