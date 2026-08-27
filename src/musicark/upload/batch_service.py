"""v0.13 format-aware facade over the sequential v0.11.1 batch coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.audio.conversion import ConversionErrorCode
from musicark.audio.formats import capabilities_for_extension
from musicark.recovery.models import RecoveryState
from musicark.recovery.service import RecoveryService

from ._batch_service_v0111 import (
    YandexBatchUploadError,
    YandexBatchUploadService as _V0111YandexBatchUploadService,
)


_CONVERSION_ERRORS = frozenset(
    {
        ConversionErrorCode.FFMPEG_NOT_AVAILABLE.value,
        ConversionErrorCode.CONVERSION_FAILED.value,
        ConversionErrorCode.CONVERSION_INVALID_OUTPUT.value,
        ConversionErrorCode.CONVERSION_CANCELLED.value,
        ConversionErrorCode.SOURCE_CHANGED.value,
    }
)
_RECOVERY_STATES = {
    RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE: "unavailable",
    RecoveryState.CENSORED_ORIGINAL_AVAILABLE: "censored",
}


class _FormatAwareLocalRepository:
    """Bypass only the legacy MP3 gate; the single-track service sees the real row."""

    def __init__(self, underlying: Any) -> None:
        self._underlying = underlying

    def get_track(self, track_id: int) -> dict[str, Any] | None:
        row = self._underlying.get_track(track_id)
        if row is None:
            return None
        item = dict(row)
        capability = capabilities_for_extension(str(item.get("extension") or ""))
        if capability is not None and (
            capability.can_upload_directly or capability.can_transcode_for_yandex
        ):
            # The v0.11.1 coordinator used this field only as an early MP3-only
            # admission gate. The actual single-track service still resolves the
            # authoritative row and performs direct-vs-convert preflight itself.
            item["extension"] = ".mp3"
        return item


class YandexBatchUploadService(_V0111YandexBatchUploadService):
    """Sequential mixed-format batch; each transfer still calls the one-track primitive."""

    def __init__(
        self,
        *,
        recovery_service: RecoveryService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._recovery = recovery_service or RecoveryService(
            self._database_path,
            repository=self._repository,
            audit_repository=self._audit,
        )
        self._local = _FormatAwareLocalRepository(self._local)

    def classify(self, local_file_ids: list[int]) -> dict[str, Any]:
        direct = 0
        convert = 0
        unsupported = 0
        items: list[dict[str, Any]] = []
        for local_file_id in dict.fromkeys(int(value) for value in local_file_ids if int(value) > 0):
            row = self._local._underlying.get_track(local_file_id)
            capability = (
                capabilities_for_extension(str(row.get("extension") or ""))
                if row is not None
                else None
            )
            if capability is not None and capability.can_upload_directly:
                mode = "direct"
                direct += 1
            elif capability is not None and capability.can_transcode_for_yandex:
                mode = "convert"
                convert += 1
            else:
                mode = "unsupported"
                unsupported += 1
            items.append({"localFileId": local_file_id, "mode": mode})
        return {
            "direct": direct,
            "convert": convert,
            "unsupported": unsupported,
            "items": items,
        }

    def _revalidate_recovery(
        self,
        *,
        source_external_id: str,
        local_file_id: int,
        playlist_kind: str,
    ) -> tuple[str, str]:
        identity = str(source_external_id or "").strip()
        if not identity:
            raise YandexBatchUploadError("Recovery source track id is required.")

        current = self._recovery.by_external_ids([identity], persist_history=False).get(identity)
        if current is None:
            raise YandexBatchUploadError(
                "Recovery state changed. Refresh Recovery before restoring this track."
            )
        role = _RECOVERY_STATES.get(current.state)
        if role is None:
            raise YandexBatchUploadError(
                "This track is no longer in a recoverable state. Refresh Recovery and try again."
            )
        if current.local_file_id != int(local_file_id):
            raise YandexBatchUploadError(
                "The local match changed after Recovery was loaded. Refresh Recovery and try again."
            )

        managed = self._repository.managed_playlists().get(role)
        current_kind = str((managed or {}).get("playlistKind") or "").strip()
        if not current_kind or current_kind != str(playlist_kind).strip():
            raise YandexBatchUploadError(
                "The MusicArk recovery playlist changed. Refresh Recovery and try again."
            )

        local = self._local._underlying.get_track(local_file_id)
        if local is None:
            raise YandexBatchUploadError("The matched local audio file is no longer available.")
        path = Path(str(local.get("path") or "")).expanduser()
        if not path.is_file():
            raise YandexBatchUploadError("The matched local audio file is no longer available.")
        capability = capabilities_for_extension(str(local.get("extension") or path.suffix))
        if capability is None or not (
            capability.can_upload_directly or capability.can_transcode_for_yandex
        ):
            raise YandexBatchUploadError(
                "The matched local audio format cannot be restored to Yandex Music safely."
            )
        return role, identity

    def _annotate_recovery_result(
        self,
        *,
        payload: dict[str, Any],
        batch_id: str,
        source_external_id: str,
        role: str,
        local_file_id: int,
        playlist_kind: str,
    ) -> dict[str, Any]:
        raw_items = payload.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        item = next(
            (
                value
                for value in items
                if isinstance(value, dict)
                and int(value.get("localFileId") or 0) == int(local_file_id)
            ),
            None,
        )
        if item is None:
            return payload

        raw_result = item.get("result")
        result = dict(raw_result) if isinstance(raw_result, dict) else {}
        status = str(item.get("status") or result.get("state") or "failed")
        result.update(
            {
                "recoverySourceProvider": "yandex_music",
                "recoverySourceExternalId": source_external_id,
                "recoveryRole": role,
            }
        )
        item["result"] = result
        item["sourceExternalId"] = source_external_id
        self._repository.update_batch_item(
            batch_id,
            int(item.get("position") or 0),
            status=status,
            result=result,
        )

        track_id = str(result.get("trackId") or "").strip() or None
        event_status = (
            "success"
            if status == "verified"
            or (status == "skipped" and str(result.get("reason") or "") == "already_uploaded")
            else status
        )
        self._audit_event(
            "recovery_restore_finished",
            batch_id,
            event_status,
            {
                "sourceProvider": "yandex_music",
                "sourceExternalId": source_external_id,
                "localFileId": int(local_file_id),
                "playlistKind": str(playlist_kind),
                "role": role,
                "restoredTrackId": track_id,
                "resultState": status,
            },
        )
        return payload

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        recovery_source = kwargs.pop("recovery_source_external_id", None)
        recovery_context: tuple[str, str, int, str] | None = None
        if recovery_source is not None:
            raw_ids = kwargs.get("local_file_ids")
            ids = list(
                dict.fromkeys(
                    int(value)
                    for value in (raw_ids if isinstance(raw_ids, list) else [])
                    if int(value) > 0
                )
            )
            if len(ids) != 1:
                raise YandexBatchUploadError(
                    "Recovery restore accepts exactly one local track at a time."
                )
            local_file_id = ids[0]
            playlist_kind = str(kwargs.get("playlist_kind") or "").strip()
            role, identity = self._revalidate_recovery(
                source_external_id=str(recovery_source),
                local_file_id=local_file_id,
                playlist_kind=playlist_kind,
            )
            # Recovery is the explicit stale-mapping recovery path. The legacy
            # coordinator still performs its normal duplicate/read-back checks,
            # but a verified mapping that disappeared from the managed playlist
            # may be uploaded again after the guard above succeeds.
            kwargs["allow_stale_reupload"] = True
            recovery_context = (role, identity, local_file_id, playlist_kind)

        payload = super().execute(**kwargs)

        if recovery_context is not None:
            role, identity, local_file_id, playlist_kind = recovery_context
            batch_id = str(payload.get("batchId") or kwargs.get("batch_id") or "").strip()
            if batch_id:
                payload = self._annotate_recovery_result(
                    payload=payload,
                    batch_id=batch_id,
                    source_external_id=identity,
                    role=role,
                    local_file_id=local_file_id,
                    playlist_kind=playlist_kind,
                )

        conversion_failed = 0
        upload_failed = 0
        for item in payload.get("items", []):
            result = item.get("result") if isinstance(item, dict) else {}
            result = result if isinstance(result, dict) else {}
            error_code = str(result.get("errorCode") or "")
            if error_code in _CONVERSION_ERRORS:
                conversion_failed += 1
            elif str(item.get("status") or "") == "failed":
                upload_failed += 1
        counts = payload.get("counts")
        if isinstance(counts, dict):
            counts["conversionFailed"] = conversion_failed
            counts["uploadFailed"] = upload_failed
        payload["conversionFailed"] = conversion_failed
        payload["uploadFailed"] = upload_failed
        return payload


__all__ = ["YandexBatchUploadError", "YandexBatchUploadService"]
