"""Isolated experimental transport for the recovered Yandex Music UGC upload flow.

Stage two is recovered with high confidence. Static data-flow analysis now also
shows that the stage-one request class obtains authorization from the normal
``common.oauth`` request configuration rather than from ``customApiToken``.
The production stage-one host/prefix is still not ground-truth verified, so the
normal MusicArk CLI remains fail-closed until an explicit profile is supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

from musicark.providers.yandex_music_provider import YandexMusicError


class YandexUploadProtocolError(YandexMusicError):
    """Raised when the recovered upload protocol cannot be followed safely."""


class YandexUploadStage1UnavailableError(YandexUploadProtocolError):
    """Raised when no verified public stage-one request profile is available."""


class YandexUploadStage1Requester(Protocol):
    """Injectable stage-one boundary used only after a profile is independently verified."""

    def post_upload_url(self, params: dict[str, str]) -> Any:
        """Return the decoded response from the recovered loader/upload-url request."""


class YandexOAuthStage1Requester:
    """Explicit OAuth requester for a ground-truth-verified Yandex stage-one prefix.

    The requester deliberately has no default host. A caller must provide the
    exact HTTPS Yandex prefix observed from the official client. Authorization
    uses the account OAuth credential because the recovered request data-flow
    links the request class to ``common.oauth`` and does not reference
    ``customApiToken`` in that authorization path.

    This class performs exactly one POST and has no retry/fallback behavior.
    It is intentionally not wired into the normal CLI until the host/profile is
    independently observed at runtime.
    """

    def __init__(
        self,
        *,
        base_url: str,
        oauth_token: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        token = str(oauth_token or "").strip()
        if not token:
            raise YandexUploadProtocolError("Stage-one OAuth credential is empty.")
        self._oauth_token = token
        self._timeout_seconds = float(timeout_seconds)
        if self._timeout_seconds <= 0:
            raise YandexUploadProtocolError("Stage-one timeout must be positive.")

    @staticmethod
    def _validate_base_url(value: str) -> str:
        clean = str(value or "").strip().rstrip("/")
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower().rstrip(".")
        yandex_host = any(
            host == suffix or host.endswith(f".{suffix}")
            for suffix in ("yandex.ru", "yandex.net", "yandex.com")
        )
        if (
            parsed.scheme != "https"
            or not host
            or not yandex_host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise YandexUploadProtocolError(
                "Stage-one base URL must be an explicit HTTPS Yandex host/prefix without credentials, query, or fragment."
            )
        return clean

    @property
    def sanitized_origin(self) -> str:
        """Return only scheme/host/path; never credential data."""
        parsed = urlparse(self._base_url)
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def post_upload_url(self, params: dict[str, str]) -> Any:
        endpoint = f"{self._base_url}/loader/upload-url"
        try:
            response = requests.post(
                endpoint,
                params=dict(params),
                headers={"Authorization": f"OAuth {self._oauth_token}"},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise YandexUploadProtocolError("Yandex stage-one OAuth request failed.") from exc

        if not 200 <= int(response.status_code) <= 299:
            raise YandexUploadProtocolError(
                f"Yandex stage-one endpoint returned HTTP {int(response.status_code)}."
            )

        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "json" in content_type:
            try:
                return response.json()
            except ValueError as exc:
                raise YandexUploadProtocolError("Yandex stage-one endpoint returned invalid JSON.") from exc

        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text
        raise YandexUploadProtocolError("Yandex stage-one endpoint returned an empty response.")


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
    """Recovered two-stage upload transport with a fail-closed stage one.

    A stage-one requester must be injected explicitly. MusicArk deliberately has
    no default requester because the production stage-one host/prefix has not yet
    been observed from the official desktop runtime. The older Android-oriented
    ``yandex-music`` request profile already failed live and is not used as a
    fallback.

    Stage two uses a fresh HTTP request without Music API OAuth/session headers,
    matching the recovered ``excludeHeaders`` / ``withoutHeaders`` behavior.
    """

    def __init__(
        self,
        stage1_requester: YandexUploadStage1Requester | None = None,
        *,
        transfer_timeout_seconds: float = 120.0,
    ) -> None:
        self._stage1_requester = stage1_requester
        self._transfer_timeout_seconds = float(transfer_timeout_seconds)

    @property
    def stage1_available(self) -> bool:
        """Whether an explicitly verified stage-one requester was supplied."""
        return self._stage1_requester is not None

    def require_stage1_profile(self) -> None:
        """Fail before an upload mutation when the official stage-one profile is unavailable."""
        if self._stage1_requester is None:
            raise YandexUploadStage1UnavailableError(
                "Yandex single-track upload stage one is BLOCKED: no ground-truth-verified "
                "desktop stage-one host/profile has been supplied. No upload request was sent."
            )

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
        raise YandexUploadProtocolError("loader/upload-url returned no usable HTTP(S) upload URL.")

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

    @staticmethod
    def build_prepare_params(
        *,
        uid: str | int,
        playlist_id: str | int,
        path: str,
        visibility: str | None = None,
    ) -> dict[str, str]:
        """Build only the statically recovered stage-one query contract."""
        clean_path = str(path).strip()
        if not clean_path:
            raise YandexUploadProtocolError("Upload path is empty.")
        params = {
            "uid": str(uid),
            "playlist-id": str(playlist_id),
            "path": clean_path,
        }
        if visibility:
            params["visibility"] = str(visibility)
        return params

    def prepare_upload(
        self,
        *,
        uid: str | int,
        playlist_id: str | int,
        path: str,
        visibility: str | None = None,
    ) -> YandexUploadSlot:
        """Request a dynamic upload URL only through an injected verified requester."""
        params = self.build_prepare_params(
            uid=uid,
            playlist_id=playlist_id,
            path=path,
            visibility=visibility,
        )
        self.require_stage1_profile()
        assert self._stage1_requester is not None
        payload = self._stage1_requester.post_upload_url(params)
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
            except ValueError:
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
