"""Managed MusicArk Yandex playlists keyed by stable role -> owned playlist kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Protocol

from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.providers.models import ProviderPlaylist
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.playlist_cache import PlaylistCacheRepository
from musicark.storage.recovery_storage import RecoveryStorageRepository


MANAGED_PLAYLIST_TITLES: dict[str, str] = {
    "censored": "ЦЕНЗУРА",
    "uploaded": "ЗАГРУЖЕННЫЕ ТРЕКИ",
}

# This must only become True after tools/yandex_playlist_research.py has produced
# a successful manual live proof for the pinned yandex-music dependency.
PLAYLIST_CREATE_LIVE_PROVEN = False


class ManagedPlaylistError(ValueError):
    pass


class ManagedPlaylistProvider(Protocol):
    def auth_check(self) -> dict[str, Any]: ...

    def get_playlist(self, external_id: str) -> tuple[ProviderPlaylist, list[Any]]: ...

    def create_playlist(self, title: str, *, visibility: str = "private") -> ProviderPlaylist: ...


ProviderFactory = Callable[[str], ManagedPlaylistProvider]


class ManagedPlaylistService:
    """Fail-closed managed-playlist bootstrap and ownership validation."""

    def __init__(
        self,
        database_path: Path,
        *,
        base_dir: Path | None = None,
        repository: RecoveryStorageRepository | None = None,
        cache: PlaylistCacheRepository | None = None,
        credential_store: CredentialStore | None = None,
        provider: ManagedPlaylistProvider | None = None,
        provider_factory: ProviderFactory | None = None,
        audit_repository: AuditLogRepository | None = None,
        creation_enabled: bool = PLAYLIST_CREATE_LIVE_PROVEN,
    ) -> None:
        self._database_path = Path(database_path)
        self._base_dir = base_dir
        self._repository = repository or RecoveryStorageRepository(self._database_path)
        self._cache = cache or PlaylistCacheRepository(self._database_path)
        self._credentials = credential_store or SystemCredentialStore()
        self._provider_override = provider
        self._provider_factory = provider_factory or (
            lambda token: YandexMusicProvider(base_dir=base_dir, token=token)
        )
        self._audit = audit_repository or AuditLogRepository(self._database_path)
        self._creation_enabled = bool(creation_enabled)

    def _provider(self) -> ManagedPlaylistProvider | None:
        if self._provider_override is not None:
            return self._provider_override
        token = self._credentials.get_token()
        if not token:
            return None
        return self._provider_factory(token)

    @staticmethod
    def _owner_uid(playlist: ProviderPlaylist) -> str | None:
        raw = playlist.raw_data if isinstance(playlist.raw_data, dict) else {}
        owner = raw.get("owner")
        if not isinstance(owner, dict):
            return None
        value = owner.get("uid")
        if value is None:
            value = owner.get("id")
        clean = str(value or "").strip()
        return clean or None

    def _owned_playlist(
        self, provider: ManagedPlaylistProvider, kind: str
    ) -> tuple[ProviderPlaylist, str]:
        account = provider.auth_check()
        uid = str(account.get("providerUserId") or "").strip()
        if not uid:
            raise ManagedPlaylistError("Yandex Music authentication is required.")
        playlist, _ = provider.get_playlist(str(kind).strip())
        owner_uid = self._owner_uid(playlist)
        if owner_uid is None or owner_uid != uid:
            raise ManagedPlaylistError("The selected playlist is not owned by the authenticated account.")
        return playlist, uid

    def _audit_event(self, event_type: str, *, role: str, kind: str) -> None:
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="managed_playlist",
                entity_id=f"{role}:{kind}",
                status="success",
                details=json.dumps(
                    {"role": role, "playlistKind": kind}, ensure_ascii=False, sort_keys=True
                ),
            )
        )

    def configured_kind(self, role: str) -> str | None:
        clean_role = str(role).strip().casefold()
        if clean_role not in MANAGED_PLAYLIST_TITLES:
            return None
        item = self._repository.managed_playlists().get(clean_role)
        return str(item.get("playlistKind") or "") if item else None

    def state(self) -> dict[str, Any]:
        configured = self._repository.managed_playlists()
        cached = self._cache.list_metadata()
        targets = [
            {
                "playlistKind": str(item.get("externalId") or ""),
                "title": str(item.get("title") or item.get("externalId") or ""),
                "trackCount": int(item.get("trackCount") or 0),
            }
            for item in cached
            if str(item.get("externalId") or "").strip()
        ]
        roles: list[dict[str, Any]] = []
        for role, default_title in MANAGED_PLAYLIST_TITLES.items():
            item = configured.get(role)
            roles.append(
                {
                    "role": role,
                    "defaultTitle": default_title,
                    "configured": item is not None,
                    "playlistKind": item.get("playlistKind") if item else None,
                    "title": item.get("title") if item else None,
                }
            )
        return {
            "canCreatePlaylists": self._creation_enabled,
            "roles": roles,
            "availablePlaylists": targets,
        }

    def set_role(self, *, role: str, playlist_kind: str) -> dict[str, Any]:
        clean_role = str(role).strip().casefold()
        if clean_role not in MANAGED_PLAYLIST_TITLES:
            raise ManagedPlaylistError("Unsupported managed playlist role.")
        provider = self._provider()
        if provider is None:
            raise ManagedPlaylistError("Yandex Music authentication is required.")
        playlist, _ = self._owned_playlist(provider, str(playlist_kind))
        self._repository.set_managed_playlist(clean_role, playlist.external_id, playlist.title)
        self._audit_event(
            "managed_playlist_adopted", role=clean_role, kind=playlist.external_id
        )
        return self.state()

    def clear_role(self, role: str) -> dict[str, Any]:
        clean_role = str(role).strip().casefold()
        if clean_role not in MANAGED_PLAYLIST_TITLES:
            raise ManagedPlaylistError("Unsupported managed playlist role.")
        self._repository.clear_managed_playlist(clean_role)
        return self.state()

    def validate_role(self, role: str) -> tuple[str, ProviderPlaylist]:
        clean_role = str(role).strip().casefold()
        if clean_role not in MANAGED_PLAYLIST_TITLES:
            raise ManagedPlaylistError("Unsupported managed playlist role.")
        kind = self.configured_kind(clean_role)
        if not kind:
            raise ManagedPlaylistError(f"Managed playlist role '{clean_role}' is not configured.")
        provider = self._provider()
        if provider is None:
            raise ManagedPlaylistError("Yandex Music authentication is required.")
        playlist, _ = self._owned_playlist(provider, kind)
        return kind, playlist

    def ensure(self, *, confirm_create: bool = False) -> dict[str, Any]:
        provider = self._provider()
        if provider is None:
            raise ManagedPlaylistError("Yandex Music authentication is required.")
        configured = self._repository.managed_playlists()
        cached = self._cache.list_metadata()
        outcomes: list[dict[str, Any]] = []

        for role, default_title in MANAGED_PLAYLIST_TITLES.items():
            persisted = configured.get(role)
            if persisted is not None:
                kind = str(persisted.get("playlistKind") or "")
                try:
                    playlist, _ = self._owned_playlist(provider, kind)
                except Exception:  # fail closed; do not silently retarget the role
                    outcomes.append({"role": role, "state": "configured_invalid", "playlistKind": kind})
                else:
                    outcomes.append(
                        {"role": role, "state": "configured", "playlistKind": kind, "title": playlist.title}
                    )
                continue

            exact = [
                item
                for item in cached
                if str(item.get("title") or "") == default_title
                and str(item.get("externalId") or "").strip()
            ]
            owned: list[ProviderPlaylist] = []
            for item in exact:
                try:
                    playlist, _ = self._owned_playlist(provider, str(item["externalId"]))
                except Exception:
                    continue
                owned.append(playlist)
            if len(owned) == 1:
                playlist = owned[0]
                self._repository.set_managed_playlist(role, playlist.external_id, playlist.title)
                self._audit_event(
                    "managed_playlist_adopted", role=role, kind=playlist.external_id
                )
                outcomes.append(
                    {"role": role, "state": "adopted", "playlistKind": playlist.external_id, "title": playlist.title}
                )
                continue
            if len(owned) > 1:
                outcomes.append(
                    {"role": role, "state": "ambiguous", "candidateCount": len(owned)}
                )
                continue
            if not self._creation_enabled:
                outcomes.append({"role": role, "state": "create_unavailable"})
                continue
            if confirm_create is not True:
                outcomes.append({"role": role, "state": "creation_confirmation_required"})
                continue

            create = getattr(provider, "create_playlist", None)
            if not callable(create):
                outcomes.append({"role": role, "state": "create_unavailable"})
                continue
            playlist = create(default_title, visibility="private")
            verified, _ = self._owned_playlist(provider, playlist.external_id)
            self._repository.set_managed_playlist(role, verified.external_id, verified.title)
            self._audit_event(
                "managed_playlist_created", role=role, kind=verified.external_id
            )
            outcomes.append(
                {"role": role, "state": "created", "playlistKind": verified.external_id, "title": verified.title}
            )

        return {**self.state(), "outcomes": outcomes}
