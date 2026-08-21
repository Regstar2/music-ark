"""Format-aware facade over the proven v0.11 single-track Yandex upload primitive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.audio.conversion import (
    AudioConversionError,
    ConversionErrorCode,
    PreparedYandexAudio,
    YandexAudioConversionService,
)
from musicark.audio.formats import capabilities_for_extension, capabilities_for_path

from ._yandex_service_v011 import (
    UploadAuditRepository,
    UploadLocalRepository,
    UploadProvider,
    YandexSingleTrackUploadService as _V011YandexSingleTrackUploadService,
    YandexUploadResult,
    YandexUploadStatus,
)


class _PreparedLocalRepository:
    """Expose one temporary MP3 to the unchanged v0.11 upload primitive."""

    def __init__(
        self,
        underlying: UploadLocalRepository,
        local_file_id: int,
        original: dict[str, Any],
        prepared: PreparedYandexAudio,
    ) -> None:
        self._underlying = underlying
        self._local_file_id = int(local_file_id)
        self._original = dict(original)
        self._prepared = prepared

    def get_track(self, track_id: int) -> dict[str, Any] | None:
        if int(track_id) != self._local_file_id:
            return self._underlying.get_track(track_id)
        row = dict(self._original)
        row["path"] = str(self._prepared.upload_path)
        row["fileName"] = self._prepared.upload_path.name
        row["extension"] = ".mp3"
        try:
            row["fileSize"] = self._prepared.upload_path.stat().st_size
        except OSError:
            row["fileSize"] = 0
        return row


class YandexSingleTrackUploadService(_V011YandexSingleTrackUploadService):
    """Keep v0.11 HTTP/read-back semantics and add a temporary conversion preflight."""

    def __init__(
        self,
        *,
        conversion_service: YandexAudioConversionService | None = None,
        **kwargs: Any,
    ) -> None:
        base_dir = kwargs.get("base_dir")
        super().__init__(**kwargs)
        self._conversion = conversion_service or YandexAudioConversionService(base_dir=base_dir)

    @staticmethod
    def _conversion_failure(
        local_file_id: int,
        playlist_kind: str,
        error: AudioConversionError,
    ) -> YandexUploadResult:
        unsupported = error.code == ConversionErrorCode.UNSUPPORTED_INPUT_FORMAT
        return YandexUploadResult(
            status=(
                YandexUploadStatus.UNSUPPORTED_FORMAT
                if unsupported
                else YandexUploadStatus.PREFLIGHT_FAILED
            ),
            local_file_id=int(local_file_id),
            playlist_kind=str(playlist_kind or "").strip(),
            error_code=error.code.value,
            safe_message=str(error),
        )

    def upload_track(
        self,
        *,
        local_file_id: int,
        playlist_kind: str,
        confirm: bool,
        rights_confirmed: bool,
    ) -> YandexUploadResult:
        # Let the proven primitive own confirmation, rights, playlist and auth errors.
        if confirm is not True or rights_confirmed is not True or not str(playlist_kind or "").strip():
            return super().upload_track(
                local_file_id=local_file_id,
                playlist_kind=playlist_kind,
                confirm=confirm,
                rights_confirmed=rights_confirmed,
            )

        track = self._local.get_track(local_file_id)
        if track is None:
            return super().upload_track(
                local_file_id=local_file_id,
                playlist_kind=playlist_kind,
                confirm=confirm,
                rights_confirmed=rights_confirmed,
            )
        source = Path(str(track.get("path") or "")).expanduser().resolve(strict=False)
        if not source.is_file() or source.stat().st_size <= 0:
            return super().upload_track(
                local_file_id=local_file_id,
                playlist_kind=playlist_kind,
                confirm=confirm,
                rights_confirmed=rights_confirmed,
            )

        capability = capabilities_for_extension(str(track.get("extension") or source.suffix))
        if capability is None:
            capability = capabilities_for_path(source)
        if capability is None:
            return YandexUploadResult(
                status=YandexUploadStatus.UNSUPPORTED_FORMAT,
                local_file_id=int(local_file_id),
                playlist_kind=str(playlist_kind).strip(),
                error_code=ConversionErrorCode.UNSUPPORTED_INPUT_FORMAT.value,
                safe_message="The selected local audio format is not supported for Yandex upload.",
            )
        if capability.can_upload_directly:
            return super().upload_track(
                local_file_id=local_file_id,
                playlist_kind=playlist_kind,
                confirm=confirm,
                rights_confirmed=rights_confirmed,
            )
        if not capability.can_transcode_for_yandex:
            return YandexUploadResult(
                status=YandexUploadStatus.UNSUPPORTED_FORMAT,
                local_file_id=int(local_file_id),
                playlist_kind=str(playlist_kind).strip(),
                error_code=ConversionErrorCode.UNSUPPORTED_INPUT_FORMAT.value,
                safe_message="The selected local audio format cannot be converted safely for Yandex upload.",
            )

        try:
            prepared = self._conversion.prepare(source)
        except AudioConversionError as exc:
            return self._conversion_failure(local_file_id, playlist_kind, exc)
        except Exception as exc:  # noqa: BLE001 - raw FFmpeg/provider details never cross the UI boundary
            return self._conversion_failure(
                local_file_id,
                playlist_kind,
                AudioConversionError(
                    ConversionErrorCode.CONVERSION_FAILED,
                    "The local audio file could not be converted safely for upload.",
                ),
            )

        original_repository = self._local
        try:
            with prepared:
                self._local = _PreparedLocalRepository(
                    original_repository,
                    local_file_id,
                    track,
                    prepared,
                )
                return super().upload_track(
                    local_file_id=local_file_id,
                    playlist_kind=playlist_kind,
                    confirm=True,
                    rights_confirmed=True,
                )
        finally:
            self._local = original_repository


__all__ = [
    "YandexSingleTrackUploadService",
    "YandexUploadResult",
    "YandexUploadStatus",
    "UploadProvider",
    "UploadLocalRepository",
    "UploadAuditRepository",
]
