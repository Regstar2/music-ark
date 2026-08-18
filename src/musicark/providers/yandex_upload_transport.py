"""Isolated experimental transport for the recovered Yandex Music UGC upload flow.

This module is intentionally not wired into provider capabilities, Sync, or the UI.
It exists only for explicit local proof-of-concept runs while production upload
support remains disabled.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from musicark.providers.yandex_music_provider import YandexMusicError


class YandexUploadProtocolError(YandexMusicError):
    """Raised when the recovered upload protocol cannot be followed safely."""


@dataclass(slots=True, frozen=True)
class YandexUploadSlot:
    """Prepared server-side upload slot returned by ``loader/upload-url``."""

    upload_url: str
    response_shape: dict[str, Any]


@dataclass(slots=True, frozen=True)
class YandexUploadTransferResult:
    """Sanitized result of sending one file to the prepared dynamic URL."""

    status_code: int
    response_shape: dict[str, Any]
    track_id: str | None = None


class YandexUploadTransport:
    """Two-stage transport recovered from the official desktop client.

    Stage one uses the authenticated Yandex Music API request boundary. Stage
    two deliberately uses a fresh HTTP request without the Music API OAuth
    headers because the official client excludes its normal headers for the
    dynamic upload URL.
    """

    def __init__(self, client: Any, *, transfer_timeout_seconds: float = 120.0) -> None:
        self._client = client
        self._transfer_timeout_seconds = float(transfer_timeout_seconds)

    @staticmethod
    def _shape(value: Any) -> dict[str, Any]:
        """Return response structure without scalar values or signed URLs."""
        if isinstance(value, dict):
            return {
                "type": "object",
                "keys": {
                    str(key): YandexUploadTransport._shape(item)
                    for key, item in value.items()
                    if str(key).lower() not in {"token", "secret", "authorization", "cookie"}
                },
            }
        if isinstance(value, list):
            sample = value[0] if value else None
            return {
                "type": "array",
                "length": len(value),
                "item": YandexUploadTransport._shape(sample) if sample is not None else {"type": "unknown"},
            }
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, (int, float)):
            return {"type": "number"}
        return {"type": "string"}

    @staticmethod
    def _extract_upload_url(payload: Any) -> str:
        candidates: list[Any] = []
        if isinstance(payload, str):
            candidates.append(payload)
        elif isinstance(payload, dict):
            candidates.append(payload.get("url"))
            result = payload.get("result")
            if isinstance(result, dict):
                candidates.append(result.get("url"))

        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            clean = candidate.strip()
            parsed = urlparse(clean)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return clean
        raise YandexUploadProtocolError(
            "loader/upload-url returned no usable HTTP(S) upload URL."
        )

    @staticmethod
    def _extract_track_id(payload: Any) -> str | None:
        """Extract an optional track identity from known shallow response shapes."""
        if not isinstance(payload, dict):
            return None
        for key in ("trackId", "track_id", "id"):
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        result = payload.get("result")
        if isinstance(result, dict):
            for key in ("trackId", "track_id", "id"):
                value = result.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
        return None

    def prepare_upload(
        self,
        *,
        uid: str | int,
        playlist_id: str | int,
        path: str,
        visibility: str | None = None,
    ) -> YandexUploadSlot:
        """Request a dynamic upload URL through the authenticated Music API."""
        clean_path = str(path).strip()
        if not clean_path:
            raise YandexUploadProtocolError("Upload path is empty.")

        params: dict[str, str] = {
            "uid": str(uid),
            "playlist-id": str(playlist_id),
            "path": clean_path,
        }
        if visibility:
            params["visibility"] = str(visibility)

        base_url = str(getattr(self._client, "base_url", "")).rstrip("/")
        request = getattr(self._client, "request", None)
        post = getattr(request, "post", None)
        if not base_url or not callable(post):
            raise YandexUploadProtocolError(
                "Authenticated Yandex client does not expose the required request boundary."
            )

        payload = post(f"{base_url}/loader/upload-url", params=params)
        return YandexUploadSlot(
            upload_url=self._extract_upload_url(payload),
            response_shape=self._shape(payload),
        )

    def upload_file(self, slot: YandexUploadSlot, file_path: Path) -> YandexUploadTransferResult:
        """POST one local file as multipart field ``file`` to the dynamic URL.

        No Yandex OAuth/session headers are copied to the dynamic host.
        """
        path = Path(file_path)
        if not path.is_file():
            raise YandexUploadProtocolError(f"Upload file does not exist: {path}")
        if path.stat().st_size <= 0:
            raise YandexUploadProtocolError("Refusing to upload an empty file.")

        try:
            with path.open("rb") as stream:
                response = requests.post(
                    slot.upload_url,
                    files={"file": (path.name, stream)},
                    timeout=self._transfer_timeout_seconds,
                )
        except requests.RequestException as exc:
            raise YandexUploadProtocolError("Dynamic Yandex upload request failed.") from exc

        response_payload: Any = None
        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "json" in content_type:
            try:
                response_payload = response.json()
            except (json.JSONDecodeError, requests.JSONDecodeError, ValueError):
                response_payload = None

        if not 200 <= response.status_code <= 299:
            raise YandexUploadProtocolError(
                f"Dynamic Yandex upload endpoint returned HTTP {response.status_code}."
            )

        return YandexUploadTransferResult(
            status_code=int(response.status_code),
            response_shape=self._shape(response_payload),
            track_id=self._extract_track_id(response_payload),
        )
