"""Isolated experimental transport for the recovered Yandex Music UGC upload flow.

The official desktop runtime has now verified the production stage-one host and
response contract. Stage one is ``POST /loader/upload-url`` on an explicit
Yandex HTTPS origin and uses account OAuth authorization. The successful desktop
response exposes ``post-target``, ``poll-result`` and ``ugc-track-id``.

The transport remains experimental and fail-closed unless a requester is
injected explicitly. No production upload capability is enabled by this module.
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


def _safe_exception_kinds(exc: BaseException) -> str:
    """Return only exception class names from a transport failure tree.

    ``requests`` often nests urllib3/http.client exceptions inside ``args`` rather
    than a normal ``__cause__`` chain. Class names are useful for distinguishing
    HTTP profile failures from TLS/socket/protocol failures without exposing a
    URL, query value, credential, proxy value, or server response body.
    """

    names: list[str] = []
    seen: set[int] = set()

    def visit(value: Any, depth: int = 0) -> None:
        if depth > 5 or not isinstance(value, BaseException) or id(value) in seen:
            return
        seen.add(id(value))
        name = type(value).__name__
        if name not in names:
            names.append(name)
        cause = value.__cause__ or value.__context__
        if cause is not None:
            visit(cause, depth + 1)
        for arg in getattr(value, "args", ()):
            visit(arg, depth + 1)

    visit(exc)
    return "/".join(names) if names else type(exc).__name__


class YandexOAuthStage1Requester:
    """Explicit OAuth requester for a ground-truth-verified Yandex stage-one prefix.

    The requester deliberately has no default host. A caller must provide the
    exact HTTPS Yandex prefix observed from the official client. Authorization
    uses the account OAuth credential because recovered request data-flow links
    the request class to ``common.oauth`` and does not reference
    ``customApiToken`` in that authorization path.

    This class performs exactly one POST and has no retry/fallback behavior.
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
                headers={
                    "Accept": "application/json",
                    "Authorization": f"OAuth {self._oauth_token}",
                },
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            kind = _safe_exception_kinds(exc)
            raise YandexUploadProtocolError(
                f"Yandex stage-one OAuth request failed (transport={kind})."
            ) from exc

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
    poll_url: str | None = None
    track_id: str | None = None


@dataclass(slots=True, frozen=True)
class YandexUploadTransferResult:
    """Sanitized result of sending one file to the prepared dynamic URL."""

    status_code: int
    response_shape: dict[str, Any]
    track_id: str | None = None


class YandexUploadTransport:
    """Recovered two-stage upload transport with a fail-closed stage one.

    A stage-one requester must still be injected explicitly. Stage two uses a
    fresh HTTP request without Music API OAuth/session headers, matching the
    recovered ``excludeHeaders`` / ``withoutHeaders`` behavior.
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
        """Fail before an upload mutation when the stage-one requester is unavailable."""
        if self._stage1_requester is None:
            raise YandexUploadStage1UnavailableError(
                "Yandex single-track upload stage one is BLOCKED: no ground-truth-verified "
                "desktop stage-one requester has been supplied. No upload request was sent."
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
    def _extract_http_url(payload: Any, keys: tuple[str, ...]) -> str | None:
        candidates: list[Any] = []
        if isinstance(payload, str) and "url" in keys:
            candidates.append(payload)
        elif isinstance(payload, dict):
            candidates.extend(payload.get(key) for key in keys)
            result = payload.get("result")
            if isinstance(result, dict):
                candidates.extend(result.get(key) for key in keys)

        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            clean = candidate.strip()
            parsed = urlparse(clean)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return clean
        return None

    @classmethod
    def _extract_upload_url(cls, payload: Any) -> str:
        url = cls._extract_http_url(payload, ("post-target", "postTarget", "url"))
        if url:
            return url
        raise YandexUploadProtocolError("loader/upload-url returned no usable HTTP(S) upload URL.")

    @classmethod
    def _extract_poll_url(cls, payload: Any) -> str | None:
        return cls._extract_http_url(payload, ("poll-result", "pollResult"))

    @staticmethod
    def _extract_track_id(payload: Any) -> str | None:
        """Extract the UGC identity from observed and legacy shallow shapes."""
        if not isinstance(payload, dict):
            return None
        keys = ("ugc-track-id", "ugcTrackId", "trackId", "track_id", "id")
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        result = payload.get("result")
        if isinstance(result, dict):
            for key in keys:
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
        """Build only the recovered stage-one query contract."""
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
            poll_url=self._extract_poll_url(payload),
            track_id=self._extract_track_id(payload),
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
            kind = _safe_exception_kinds(exc)
            raise YandexUploadProtocolError(
                f"Dynamic Yandex upload request failed (transport={kind})."
            ) from exc

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
