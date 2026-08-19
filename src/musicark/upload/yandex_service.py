"""Production manual single-track Yandex Music upload orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import time
from typing import Any, Callable, Protocol

from musicark.core.config import load_config
from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.providers.yandex_music_provider import YandexMusicError, YandexMusicProvider
from musicark.providers.yandex_upload_transport import (
    YandexDirectUploadTransport,
    YandexUploadHttpError,
    YandexUploadNetworkError,
    YandexUploadProtocolError,
)
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


class YandexUploadStatus(StrEnum):
    """Stable result states exposed to bridges and Flutter."""

    VERIFIED = "verified"
    PROCESSING = "processing"
    DELIVERY_UNKNOWN = "delivery_unknown"
    STAGE1_FAILED = "stage1_failed"
    STAGE2_HTTP_FAILED = "stage2_http_failed"
    PREFLIGHT_FAILED = "preflight_failed"
    UNSUPPORTED_FORMAT = "unsupported_format"
    AMBIGUOUS = "ambiguous"


@dataclass(slots=True, frozen=True)
class YandexUploadResult:
    """Credential-free upload outcome safe for JSON/UI serialization."""

    status: YandexUploadStatus
    local_file_id: int
    playlist_kind: str
    track_id: str | None = None
    stage1_http_status: int | None = None
    stage2_http_status: int | None = None
    read_back_verified: bool = False
    read_back_attempts: int = 0
    error_code: str | None = None
    safe_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "localFileId": self.local_file_id,
            "playlistKind": self.playlist_kind,
            "trackId": self.track_id,
            "stage1HttpStatus": self.stage1_http_status,
            "stage2HttpStatus": self.stage2_http_status,
            "readBackVerified": self.read_back_verified,
            "readBackAttempts": self.read_back_attempts,
            "errorCode": self.error_code,
            "safeMessage": self.safe_message,
        }


class UploadProvider(Protocol):
    def auth_check(self) -> dict[str, Any]: ...

    def get_playlist(self, external_id: str) -> tuple[ProviderPlaylist, list[ProviderTrack]]: ...


class UploadLocalRepository(Protocol):
    def get_track(self, track_id: int) -> dict[str, Any] | None: ...


class UploadAuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...


ProviderFactory = Callable[[str], UploadProvider]
Sleeper = Callable[[float], None]


class YandexSingleTrackUploadService:
    """Fail-closed production application service for one manual MP3 upload."""

    DEFAULT_READ_BACK_ATTEMPTS = 15
    DEFAULT_READ_BACK_INTERVAL_SECONDS = 2.0

    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        credential_store: CredentialStore | None = None,
        provider: UploadProvider | None = None,
        provider_factory: ProviderFactory | None = None,
        transport: YandexDirectUploadTransport | None = None,
        local_repository: UploadLocalRepository | None = None,
        audit_repository: UploadAuditRepository | None = None,
        read_back_attempts: int = DEFAULT_READ_BACK_ATTEMPTS,
        read_back_interval_seconds: float = DEFAULT_READ_BACK_INTERVAL_SECONDS,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self._base_dir = base_dir
        self._credentials = credential_store or SystemCredentialStore()
        self._provider_override = provider
        self._provider_factory = provider_factory or (
            lambda token: YandexMusicProvider(base_dir=base_dir, token=token)
        )
        self._transport = transport or YandexDirectUploadTransport()
        database_path = self._resolve_database_path()
        self._local = local_repository or LocalLibraryStorageRepository(database_path)
        self._audit = audit_repository or AuditLogRepository(database_path)
        if read_back_attempts <= 0:
            raise ValueError("read_back_attempts must be positive")
        if read_back_interval_seconds < 0:
            raise ValueError("read_back_interval_seconds cannot be negative")
        self._read_back_attempts = int(read_back_attempts)
        self._read_back_interval_seconds = float(read_back_interval_seconds)
        self._sleeper = sleeper

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        configured = Path(config.database_path)
        if configured.is_absolute():
            return configured
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / configured

    def _provider(self) -> UploadProvider | None:
        if self._provider_override is not None:
            return self._provider_override
        token = self._credentials.get_token()
        if not token:
            return None
        return self._provider_factory(token)

    @staticmethod
    def _playlist_owner_uid(playlist: ProviderPlaylist) -> str | None:
        raw = playlist.raw_data if isinstance(playlist.raw_data, dict) else {}
        owner = raw.get("owner")
        if not isinstance(owner, dict):
            return None
        value = owner.get("uid")
        if value is None:
            value = owner.get("id")
        clean = str(value or "").strip()
        return clean or None

    @staticmethod
    def _track_ids(tracks: list[ProviderTrack]) -> set[str]:
        return {
            str(item.external_id).strip()
            for item in tracks
            if str(item.external_id).strip()
        }

    @staticmethod
    def _preflight_result(
        local_file_id: int,
        playlist_kind: str,
        error_code: str,
        message: str,
        *,
        unsupported: bool = False,
    ) -> YandexUploadResult:
        return YandexUploadResult(
            status=(
                YandexUploadStatus.UNSUPPORTED_FORMAT
                if unsupported
                else YandexUploadStatus.PREFLIGHT_FAILED
            ),
            local_file_id=local_file_id,
            playlist_kind=playlist_kind,
            error_code=error_code,
            safe_message=message,
        )

    def _audit_event(
        self,
        event_type: str,
        *,
        local_file_id: int,
        playlist_kind: str,
        status: str,
        error_code: str | None = None,
    ) -> None:
        details: dict[str, Any] = {
            "localFileId": local_file_id,
            "playlistKind": playlist_kind,
        }
        if error_code:
            details["errorCode"] = error_code
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="local_audio_file",
                entity_id=str(local_file_id),
                status=status,
                details=json.dumps(details, ensure_ascii=False, sort_keys=True),
            )
        )

    def _verify_read_back(
        self,
        provider: UploadProvider,
        *,
        playlist_kind: str,
        before_track_ids: set[str],
        ugc_track_id: str | None,
    ) -> tuple[YandexUploadStatus, str | None, int]:
        """Bounded playlist read-back; read failures never trigger upload retries."""
        attempts = 0
        for index in range(self._read_back_attempts):
            attempts = index + 1
            try:
                _, tracks = provider.get_playlist(playlist_kind)
            except Exception:  # noqa: BLE001 - read-back is deliberately best effort
                tracks = []
            current_ids = self._track_ids(tracks)
            if ugc_track_id and ugc_track_id in current_ids:
                return YandexUploadStatus.VERIFIED, ugc_track_id, attempts
            new_ids = current_ids - before_track_ids
            if len(new_ids) == 1:
                return YandexUploadStatus.VERIFIED, next(iter(new_ids)), attempts
            if len(new_ids) > 1:
                return YandexUploadStatus.AMBIGUOUS, None, attempts
            if index + 1 < self._read_back_attempts:
                self._sleeper(self._read_back_interval_seconds)
        return YandexUploadStatus.PROCESSING, ugc_track_id, attempts

    def upload_track(
        self,
        *,
        local_file_id: int,
        playlist_kind: str,
        confirm: bool,
        rights_confirmed: bool,
    ) -> YandexUploadResult:
        """Upload one indexed MP3 after all fail-closed preflight checks."""
        kind = str(playlist_kind or "").strip()
        if confirm is not True:
            return self._preflight_result(
                local_file_id,
                kind,
                "confirmation_required",
                "Explicit upload confirmation is required.",
            )
        if rights_confirmed is not True:
            return self._preflight_result(
                local_file_id,
                kind,
                "rights_confirmation_required",
                "Rights confirmation is required before upload.",
            )
        if not kind:
            return self._preflight_result(
                local_file_id,
                kind,
                "playlist_required",
                "A target Yandex Music playlist is required.",
            )

        track = self._local.get_track(local_file_id)
        if track is None:
            return self._preflight_result(
                local_file_id,
                kind,
                "invalid_local_file_id",
                "The selected local track is no longer available.",
            )
        file_path = Path(str(track.get("path") or ""))
        if not file_path.is_file():
            return self._preflight_result(
                local_file_id,
                kind,
                "missing_file",
                "The selected local audio file does not exist on disk.",
            )
        try:
            file_size = file_path.stat().st_size
        except OSError:
            file_size = 0
        if file_size <= 0:
            return self._preflight_result(
                local_file_id,
                kind,
                "empty_file",
                "The selected local audio file is empty or unreadable.",
            )
        extension = str(track.get("extension") or file_path.suffix).strip().lower()
        if not extension.startswith("."):
            extension = f".{extension}" if extension else file_path.suffix.lower()
        if extension != ".mp3" or file_path.suffix.lower() != ".mp3":
            return self._preflight_result(
                local_file_id,
                kind,
                "unsupported_format",
                "MusicArk v0.11.0 supports manual Yandex upload for MP3 files only.",
                unsupported=True,
            )

        provider = self._provider()
        if provider is None:
            return self._preflight_result(
                local_file_id,
                kind,
                "auth_required",
                "Yandex Music authentication is required.",
            )
        try:
            account = provider.auth_check()
            uid = str(account.get("providerUserId") or "").strip()
        except Exception:  # noqa: BLE001 - credentials/provider details stay behind safe boundary
            uid = ""
        if not uid:
            return self._preflight_result(
                local_file_id,
                kind,
                "auth_required",
                "Yandex Music authentication is required.",
            )

        try:
            playlist, before_tracks = provider.get_playlist(kind)
        except YandexMusicError:
            return self._preflight_result(
                local_file_id,
                kind,
                "playlist_unavailable",
                "The selected Yandex Music playlist is unavailable.",
            )
        except Exception:  # noqa: BLE001
            return self._preflight_result(
                local_file_id,
                kind,
                "playlist_unavailable",
                "The selected Yandex Music playlist is unavailable.",
            )

        owner_uid = self._playlist_owner_uid(playlist)
        if playlist.external_id != kind or owner_uid is None or owner_uid != uid:
            return self._preflight_result(
                local_file_id,
                kind,
                "playlist_not_owned",
                "The selected playlist is not owned by the authenticated Yandex Music account.",
            )

        before_track_ids = self._track_ids(before_tracks)
        self._audit_event(
            "upload_started",
            local_file_id=local_file_id,
            playlist_kind=kind,
            status="started",
        )

        try:
            slot = self._transport.prepare_upload(
                uid=uid,
                playlist_kind=kind,
                file_path=file_path,
            )
        except YandexUploadHttpError as exc:
            result = YandexUploadResult(
                status=YandexUploadStatus.STAGE1_FAILED,
                local_file_id=local_file_id,
                playlist_kind=kind,
                stage1_http_status=exc.status_code,
                error_code="stage1_http_failed",
                safe_message="Yandex Music could not prepare the upload.",
            )
            self._audit_event(
                "upload_failed",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="failed",
                error_code=result.error_code,
            )
            return result
        except (YandexUploadNetworkError, YandexUploadProtocolError):
            result = YandexUploadResult(
                status=YandexUploadStatus.STAGE1_FAILED,
                local_file_id=local_file_id,
                playlist_kind=kind,
                error_code="stage1_failed",
                safe_message="Yandex Music could not prepare the upload.",
            )
            self._audit_event(
                "upload_failed",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="failed",
                error_code=result.error_code,
            )
            return result

        try:
            transfer = self._transport.upload_file(slot, file_path)
        except YandexUploadNetworkError:
            verification, verified_track_id, attempts = self._verify_read_back(
                provider,
                playlist_kind=kind,
                before_track_ids=before_track_ids,
                ugc_track_id=slot.ugc_track_id,
            )
            if verification == YandexUploadStatus.VERIFIED:
                result = YandexUploadResult(
                    status=YandexUploadStatus.VERIFIED,
                    local_file_id=local_file_id,
                    playlist_kind=kind,
                    track_id=verified_track_id,
                    stage1_http_status=slot.status_code,
                    read_back_verified=True,
                    read_back_attempts=attempts,
                    safe_message="The track was uploaded and verified in the selected playlist.",
                )
                self._audit_event(
                    "upload_verified",
                    local_file_id=local_file_id,
                    playlist_kind=kind,
                    status="verified",
                )
                return result
            if verification == YandexUploadStatus.AMBIGUOUS:
                result = YandexUploadResult(
                    status=YandexUploadStatus.AMBIGUOUS,
                    local_file_id=local_file_id,
                    playlist_kind=kind,
                    track_id=slot.ugc_track_id,
                    stage1_http_status=slot.status_code,
                    read_back_attempts=attempts,
                    error_code="read_back_ambiguous",
                    safe_message="The upload outcome is ambiguous; check the target playlist before trying again.",
                )
                self._audit_event(
                    "upload_failed",
                    local_file_id=local_file_id,
                    playlist_kind=kind,
                    status="ambiguous",
                    error_code=result.error_code,
                )
                return result
            result = YandexUploadResult(
                status=YandexUploadStatus.DELIVERY_UNKNOWN,
                local_file_id=local_file_id,
                playlist_kind=kind,
                track_id=slot.ugc_track_id,
                stage1_http_status=slot.status_code,
                read_back_attempts=attempts,
                error_code="delivery_unknown",
                safe_message=(
                    "The connection was interrupted during upload. It is not possible to determine "
                    "whether the file was accepted. Check the playlist before trying again."
                ),
            )
            self._audit_event(
                "upload_delivery_unknown",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="delivery_unknown",
                error_code=result.error_code,
            )
            return result
        except YandexUploadHttpError as exc:
            result = YandexUploadResult(
                status=YandexUploadStatus.STAGE2_HTTP_FAILED,
                local_file_id=local_file_id,
                playlist_kind=kind,
                track_id=slot.ugc_track_id,
                stage1_http_status=slot.status_code,
                stage2_http_status=exc.status_code,
                error_code="stage2_http_failed",
                safe_message="Yandex Music did not accept the upload.",
            )
            self._audit_event(
                "upload_failed",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="failed",
                error_code=result.error_code,
            )
            return result
        except YandexUploadProtocolError:
            result = YandexUploadResult(
                status=YandexUploadStatus.STAGE2_HTTP_FAILED,
                local_file_id=local_file_id,
                playlist_kind=kind,
                track_id=slot.ugc_track_id,
                stage1_http_status=slot.status_code,
                error_code="stage2_protocol_failed",
                safe_message="Yandex Music could not complete the upload safely.",
            )
            self._audit_event(
                "upload_failed",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="failed",
                error_code=result.error_code,
            )
            return result

        verification, verified_track_id, attempts = self._verify_read_back(
            provider,
            playlist_kind=kind,
            before_track_ids=before_track_ids,
            ugc_track_id=slot.ugc_track_id,
        )
        if verification == YandexUploadStatus.VERIFIED:
            result = YandexUploadResult(
                status=YandexUploadStatus.VERIFIED,
                local_file_id=local_file_id,
                playlist_kind=kind,
                track_id=verified_track_id,
                stage1_http_status=slot.status_code,
                stage2_http_status=transfer.status_code,
                read_back_verified=True,
                read_back_attempts=attempts,
                safe_message="The track was uploaded and verified in the selected playlist.",
            )
            self._audit_event(
                "upload_verified",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="verified",
            )
            return result
        if verification == YandexUploadStatus.AMBIGUOUS:
            result = YandexUploadResult(
                status=YandexUploadStatus.AMBIGUOUS,
                local_file_id=local_file_id,
                playlist_kind=kind,
                track_id=slot.ugc_track_id,
                stage1_http_status=slot.status_code,
                stage2_http_status=transfer.status_code,
                read_back_attempts=attempts,
                error_code="read_back_ambiguous",
                safe_message="The upload completed, but playlist verification was ambiguous.",
            )
            self._audit_event(
                "upload_failed",
                local_file_id=local_file_id,
                playlist_kind=kind,
                status="ambiguous",
                error_code=result.error_code,
            )
            return result

        result = YandexUploadResult(
            status=YandexUploadStatus.PROCESSING,
            local_file_id=local_file_id,
            playlist_kind=kind,
            track_id=slot.ugc_track_id,
            stage1_http_status=slot.status_code,
            stage2_http_status=transfer.status_code,
            read_back_attempts=attempts,
            safe_message="The file was uploaded and is still processing in Yandex Music.",
        )
        self._audit_event(
            "upload_processing",
            local_file_id=local_file_id,
            playlist_kind=kind,
            status="processing",
        )
        return result
