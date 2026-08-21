"""v0.13 format-aware facade over the sequential v0.11.1 batch coordinator."""

from __future__ import annotations

from typing import Any

from musicark.audio.conversion import ConversionErrorCode
from musicark.audio.formats import capabilities_for_extension

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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
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

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        payload = super().execute(**kwargs)
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
