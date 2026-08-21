"""v0.13 format-aware Local Library facade over the existing index/query service."""

from __future__ import annotations

from typing import Any

from musicark.audio.formats import capabilities_for_extension

from ._service_v012 import LocalLibraryService as _V012LocalLibraryService


class LocalLibraryService(_V012LocalLibraryService):
    """Annotate rows from the central capability registry without re-probing the library."""

    @staticmethod
    def _attach_audio_capabilities(items: list[dict[str, Any]]) -> None:
        for item in items:
            capability = capabilities_for_extension(str(item.get("extension") or ""))
            if capability is None:
                item["format"] = str(item.get("extension") or "").lstrip(".").upper()
                item["formatCapabilities"] = None
                item["uploadMode"] = "unsupported"
            else:
                item["format"] = capability.display_name
                item["formatCapabilities"] = capability.to_dict()
                if capability.can_upload_directly:
                    item["uploadMode"] = "direct"
                elif capability.can_transcode_for_yandex:
                    item["uploadMode"] = "convert"
                else:
                    item["uploadMode"] = "unsupported"
            item["technical"] = {
                "codec": item.get("codec"),
                "durationSeconds": item.get("durationSeconds"),
                "bitrate": item.get("bitrate"),
                "sampleRate": item.get("sampleRate"),
            }

    def tracks(self, **kwargs: Any) -> dict[str, Any]:
        payload = super().tracks(**kwargs)
        items = payload.get("items")
        if isinstance(items, list):
            self._attach_audio_capabilities(items)
        return payload

    def track(self, track_id: int) -> dict[str, Any]:
        payload = super().track(track_id)
        item = payload.get("track")
        if isinstance(item, dict):
            self._attach_audio_capabilities([item])
        return payload


__all__ = ["LocalLibraryService"]
