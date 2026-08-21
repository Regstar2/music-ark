"""Sequential v0.11.1 batch coordinator built on YandexSingleTrackUploadService."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from musicark.core.config import load_config
from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.providers.yandex_music_provider import YandexMusicProvider
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.storage.recovery_storage import RecoveryStorageRepository

from .yandex_service import YandexSingleTrackUploadService, YandexUploadResult, YandexUploadStatus


class YandexBatchUploadError(ValueError):
    pass


class BatchProvider(Protocol):
    def auth_check(self) -> dict[str, Any]: ...

    def get_playlist(self, external_id: str) -> tuple[ProviderPlaylist, list[ProviderTrack]]: ...


ProviderFactory = Callable[[str], BatchProvider]


@dataclass(slots=True, frozen=True)
class _ExistingMembership:
    readable: bool
    track_ids: frozenset[str]


class YandexBatchUploadService:
    """Execute one explicit batch sequentially; concurrency is intentionally fixed at one."""

    MAX_BATCH_SIZE = 500

    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        database_path: Path | None = None,
        single_track_service: YandexSingleTrackUploadService | None = None,
        repository: RecoveryStorageRepository | None = None,
        local_repository: LocalLibraryStorageRepository | None = None,
        audit_repository: AuditLogRepository | None = None,
        credential_store: CredentialStore | None = None,
        provider: BatchProvider | None = None,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        self._single = single_track_service or YandexSingleTrackUploadService(base_dir=base_dir)
        self._repository = repository or RecoveryStorageRepository(self._database_path)
        self._local = local_repository or LocalLibraryStorageRepository(self._database_path)
        self._audit = audit_repository or AuditLogRepository(self._database_path)
        self._credentials = credential_store or SystemCredentialStore()
        self._provider_override = provider
        self._provider_factory = provider_factory or (
            lambda token: YandexMusicProvider(base_dir=base_dir, token=token)
        )

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def _provider(self) -> BatchProvider | None:
        if self._provider_override is not None:
            return self._provider_override
        token = self._credentials.get_token()
        if not token:
            return None
        return self._provider_factory(token)

    def _existing_membership(self, playlist_kind: str) -> _ExistingMembership:
        provider = self._provider()
        if provider is None:
            return _ExistingMembership(False, frozenset())
        try:
            _, tracks = provider.get_playlist(playlist_kind)
        except Exception:  # noqa: BLE001 - duplicate protection fails closed
            return _ExistingMembership(False, frozenset())
        return _ExistingMembership(
            True,
            frozenset(str(track.external_id) for track in tracks if str(track.external_id).strip()),
        )

    @staticmethod
    def _base_counts() -> dict[str, int]:
        return {
            "total": 0,
            "verified": 0,
            "processing": 0,
            "deliveryUnknown": 0,
            "failed": 0,
            "unsupported": 0,
            "ambiguous": 0,
            "skipped": 0,
            "cancelled": 0,
        }

    def _audit_event(self, event_type: str, batch_id: str, status: str, details: dict[str, Any]) -> None:
        safe = {
            key: value
            for key, value in details.items()
            if key not in {"path", "filePath", "token", "uid", "Authorization", "Cookie"}
        }
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="upload_batch",
                entity_id=batch_id,
                status=status,
                details=json.dumps(safe, ensure_ascii=False, sort_keys=True)[:16000],
            )
        )

    @staticmethod
    def _result_status(result: YandexUploadResult) -> str:
        if result.status == YandexUploadStatus.VERIFIED:
            return "verified"
        if result.status == YandexUploadStatus.PROCESSING:
            return "processing"
        if result.status == YandexUploadStatus.DELIVERY_UNKNOWN:
            return "delivery_unknown"
        if result.status == YandexUploadStatus.UNSUPPORTED_FORMAT:
            return "unsupported"
        if result.status == YandexUploadStatus.AMBIGUOUS:
            return "ambiguous"
        return "failed"

    @staticmethod
    def _count_key(status: str) -> str:
        return {
            "delivery_unknown": "deliveryUnknown",
            "unsupported": "unsupported",
            "ambiguous": "ambiguous",
            "verified": "verified",
            "processing": "processing",
            "skipped": "skipped",
            "cancelled": "cancelled",
        }.get(status, "failed")

    def execute(
        self,
        *,
        local_file_ids: list[int],
        playlist_kind: str,
        confirm: bool,
        rights_confirmed: bool,
        batch_id: str | None = None,
        allow_stale_reupload: bool = False,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise YandexBatchUploadError("Batch upload requires explicit confirmation.")
        if rights_confirmed is not True:
            raise YandexBatchUploadError("Batch upload requires explicit upload-rights confirmation.")
        ids = list(dict.fromkeys(int(value) for value in local_file_ids if int(value) > 0))
        if not ids:
            raise YandexBatchUploadError("At least one local_file_id is required.")
        if len(ids) > self.MAX_BATCH_SIZE:
            raise YandexBatchUploadError(f"Batch is limited to {self.MAX_BATCH_SIZE} local files.")
        kind = str(playlist_kind).strip()
        if not kind:
            raise YandexBatchUploadError("playlist_kind is required.")
        identifier = str(batch_id or uuid4()).strip()
        if not identifier or len(identifier) > 128:
            raise YandexBatchUploadError("batch_id is invalid.")

        self._repository.create_batch(identifier, kind, ids)
        counts = self._base_counts()
        counts["total"] = len(ids)
        self._audit_event(
            "upload_batch_started",
            identifier,
            "success",
            {"playlistKind": kind, "total": len(ids), "concurrency": 1},
        )

        mappings = self._repository.upload_mappings(ids, kind)
        membership = self._existing_membership(kind)
        known_track_ids = set(membership.track_ids)
        completed = 0
        cancelled = False

        for position, local_file_id in enumerate(ids):
            if self._repository.cancel_requested(identifier):
                cancelled = True
                for remaining_position in range(position, len(ids)):
                    self._repository.update_batch_item(
                        identifier,
                        remaining_position,
                        status="cancelled",
                        result={"state": "cancelled", "reason": "cancelled_before_start"},
                    )
                    counts["cancelled"] += 1
                break

            local = self._local.get_track(local_file_id)
            if local is not None and str(local.get("extension") or "").casefold() != ".mp3":
                item = {
                    "state": "unsupported",
                    "reason": "mp3_only",
                    "localFileId": local_file_id,
                    "playlistKind": kind,
                }
                self._repository.update_batch_item(identifier, position, status="unsupported", result=item)
                counts["unsupported"] += 1
                completed += 1
                continue

            mapping = mappings.get(local_file_id)
            if mapping is not None:
                mapped_status = str(mapping.get("status") or "")
                mapped_track_id = str(mapping.get("trackId") or "").strip()
                if mapped_track_id and membership.readable and mapped_track_id in known_track_ids:
                    item = {
                        "state": "skipped",
                        "reason": "already_uploaded",
                        "localFileId": local_file_id,
                        "playlistKind": kind,
                        "trackId": mapped_track_id,
                    }
                    self._repository.update_batch_item(identifier, position, status="skipped", result=item)
                    counts["skipped"] += 1
                    completed += 1
                    continue
                if mapped_status in {"delivery_unknown", "ambiguous", "processing"}:
                    item = {
                        "state": "skipped",
                        "reason": "manual_playlist_check_required",
                        "localFileId": local_file_id,
                        "playlistKind": kind,
                        "trackId": mapped_track_id or None,
                    }
                    self._repository.update_batch_item(identifier, position, status="skipped", result=item)
                    counts["skipped"] += 1
                    completed += 1
                    continue
                if mapped_status == "verified" and not membership.readable:
                    item = {
                        "state": "skipped",
                        "reason": "duplicate_check_unavailable",
                        "localFileId": local_file_id,
                        "playlistKind": kind,
                    }
                    self._repository.update_batch_item(identifier, position, status="skipped", result=item)
                    counts["skipped"] += 1
                    completed += 1
                    continue
                if mapped_status == "verified" and not allow_stale_reupload:
                    item = {
                        "state": "skipped",
                        "reason": "stale_mapping_requires_explicit_recovery",
                        "localFileId": local_file_id,
                        "playlistKind": kind,
                    }
                    self._repository.update_batch_item(identifier, position, status="skipped", result=item)
                    counts["skipped"] += 1
                    completed += 1
                    continue

            try:
                result = self._single.upload_track(
                    local_file_id=local_file_id,
                    playlist_kind=kind,
                    confirm=True,
                    rights_confirmed=True,
                )
                status = self._result_status(result)
                item = result.to_dict()
            except Exception:  # noqa: BLE001 - isolate one item and never leak provider exception text
                status = "failed"
                item = {
                    "state": "failed",
                    "reason": "single_track_upload_failed",
                    "localFileId": local_file_id,
                    "playlistKind": kind,
                }
            else:
                item["state"] = status
                if result.track_id and status in {
                    "verified",
                    "processing",
                    "delivery_unknown",
                    "ambiguous",
                }:
                    self._repository.upsert_upload_mapping(
                        local_file_id=local_file_id,
                        playlist_kind=kind,
                        track_id=result.track_id,
                        status=status,
                        verified=status == "verified",
                    )
                    if status == "verified":
                        known_track_ids.add(result.track_id)
            self._repository.update_batch_item(identifier, position, status=status, result=item)
            counts[self._count_key(status)] += 1
            completed += 1

        final_status = "cancelled" if cancelled else ("partial" if counts["failed"] else "finished")
        self._repository.finish_batch(
            identifier,
            status=final_status,
            completed=completed,
            counts=counts,
        )
        self._audit_event(
            "upload_batch_cancelled" if cancelled else "upload_batch_finished",
            identifier,
            "cancelled" if cancelled else ("partial" if counts["failed"] else "success"),
            {"playlistKind": kind, **counts},
        )
        payload = self._repository.batch(identifier)
        assert payload is not None
        payload["concurrency"] = 1
        payload["retryableLocalFileIds"] = [
            int(item["localFileId"])
            for item in payload["items"]
            if str(item.get("status")) == "failed"
        ]
        payload["manualCheckLocalFileIds"] = [
            int(item["localFileId"])
            for item in payload["items"]
            if str(item.get("result", {}).get("reason")) == "manual_playlist_check_required"
            or str(item.get("status")) in {"delivery_unknown", "ambiguous", "processing"}
        ]
        return payload

    def status(self, batch_id: str) -> dict[str, Any]:
        payload = self._repository.batch(str(batch_id))
        if payload is None:
            raise YandexBatchUploadError("Upload batch was not found.")
        payload["concurrency"] = 1
        return payload

    def cancel(self, batch_id: str) -> dict[str, Any]:
        identifier = str(batch_id).strip()
        if not identifier:
            raise YandexBatchUploadError("batch_id is required.")
        accepted = self._repository.request_cancel(identifier)
        payload = self._repository.batch(identifier)
        if payload is None:
            raise YandexBatchUploadError("Upload batch was not found.")
        return {"accepted": accepted, "batch": payload}
