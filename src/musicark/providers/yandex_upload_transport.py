"""Yandex Music UGC upload transports.

``YandexDirectUploadTransport`` is the production v0.11.0 transport. It follows
only the direct protocol verified by the v0.10.0 live Python proof: one fixed
stage-one request, one multipart stage-two request, no credentials on either
request and no automatic retry.

The older ``YandexUploadTransport`` and ``YandexOAuthStage1Requester`` symbols
remain as deprecated research compatibility boundaries. Production code must not
use them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

import httpx
import requests

from musicark.providers.yandex_music_provider import YandexMusicError


YANDEX_DIRECT_UPLOAD_URL = "https://api.music.yandex.net/loader/upload-url"
_ALLOWED_YANDEX_DOMAINS = ("yandex.ru", "yandex.net", "yandex.com")


class YandexUploadProtocolError(YandexMusicError):
    """Raised when the upload protocol cannot be followed safely."""


class YandexUploadNetworkError(YandexUploadProtocolError):
    """Sanitized transport failure that intentionally omits URL/error text."""

    def __init__(self, stage: str, exception_type: str) -> None:
        super().__init__(f"Yandex upload {stage} transport failed ({exception_type}).")
        self.stage = stage
        self.exception_type = exception_type


class YandexUploadHttpError(YandexUploadProtocolError):
    """HTTP status failure without response body or signed URL exposure."""

    def __init__(self, stage: str, status_code: int) -> None:
        super().__init__(f"Yandex upload {stage} returned HTTP {status_code}.")
        self.stage = stage
        self.status_code = int(status_code)


class YandexUploadStage1UnavailableError(YandexUploadProtocolError):
    """Raised by the deprecated research transport when no requester exists."""


@dataclass(slots=True, frozen=True)
class YandexDirectUploadSlot:
    """Internal stage-one response; signed URLs must never cross the service boundary."""

    post_target: str
    poll_result: str | None
    ugc_track_id: str | None
    status_code: int


@dataclass(slots=True, frozen=True)
class YandexDirectUploadTransferResult:
    """Sanitized successful stage-two response metadata."""

    status_code: int


HttpxClientFactory = Callable[..., httpx.Client]


class YandexDirectUploadTransport:
    """Production two-stage single-file upload transport for v0.11.0."""

    def __init__(
        self,
        *,
        stage1_timeout_seconds: float = 30.0,
        stage2_timeout_seconds: float = 120.0,
        client_factory: HttpxClientFactory = httpx.Client,
    ) -> None:
        if stage1_timeout_seconds <= 0 or stage2_timeout_seconds <= 0:
            raise ValueError("Upload timeouts must be positive.")
        self._stage1_timeout_seconds = float(stage1_timeout_seconds)
        self._stage2_timeout_seconds = float(stage2_timeout_seconds)
        self._client_factory = client_factory

    def _client(self, timeout_seconds: float) -> httpx.Client:
        return self._client_factory(
            http1=True,
            http2=True,
            trust_env=False,
            follow_redirects=False,
            timeout=timeout_seconds,
        )

    @staticmethod
    def validate_post_target(value: str) -> str:
        """Allow only credential-free HTTPS URLs hosted by Yandex domains."""
        clean = str(value or "").strip()
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed_host = any(
            host == suffix or host.endswith(f".{suffix}")
            for suffix in _ALLOWED_YANDEX_DOMAINS
        )
        if (
            parsed.scheme.lower() != "https"
            or not host
            or not allowed_host
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise YandexUploadProtocolError(
                "Stage-two target must be a credential-free HTTPS Yandex URL."
            )
        return clean

    @staticmethod
    def _required_string(payload: Any, key: str) -> str:
        if not isinstance(payload, dict):
            raise YandexUploadProtocolError("Stage-one response must be a JSON object.")
        value = payload.get(key)
        clean = str(value or "").strip()
        if not clean:
            raise YandexUploadProtocolError(f"Stage-one response is missing {key}.")
        return clean

    def prepare_upload(
        self,
        *,
        uid: str | int,
        playlist_kind: str | int,
        file_path: Path,
    ) -> YandexDirectUploadSlot:
        """Perform exactly one credential-free stage-one request."""
        path = Path(file_path)
        params = {
            "uid": str(uid),
            "playlist-id": f"{uid}:{playlist_kind}",
            "path": path.name,
        }
        try:
            with self._client(self._stage1_timeout_seconds) as client:
                response = client.post(YANDEX_DIRECT_UPLOAD_URL, params=params)
        except httpx.HTTPError as exc:
            raise YandexUploadNetworkError("stage1", type(exc).__name__) from exc

        status_code = int(response.status_code)
        if status_code != 200:
            raise YandexUploadHttpError("stage1", status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise YandexUploadProtocolError("Stage-one response contained invalid JSON.") from exc

        post_target = self.validate_post_target(self._required_string(payload, "post-target"))
        poll_result_raw = payload.get("poll-result") if isinstance(payload, dict) else None
        track_id_raw = payload.get("ugc-track-id") if isinstance(payload, dict) else None
        poll_result = str(poll_result_raw).strip() if poll_result_raw is not None else None
        ugc_track_id = str(track_id_raw).strip() if track_id_raw is not None else None
        return YandexDirectUploadSlot(
            post_target=post_target,
            poll_result=poll_result or None,
            ugc_track_id=ugc_track_id or None,
            status_code=status_code,
        )

    def upload_file(
        self,
        slot: YandexDirectUploadSlot,
        file_path: Path,
    ) -> YandexDirectUploadTransferResult:
        """Perform exactly one multipart stage-two POST without auth/session headers."""
        path = Path(file_path)
        target = self.validate_post_target(slot.post_target)
        try:
            with path.open("rb") as stream:
                with self._client(self._stage2_timeout_seconds) as client:
                    response = client.post(
                        target,
                        files={"file": (path.name, stream)},
                    )
        except httpx.HTTPError as exc:
            raise YandexUploadNetworkError("stage2", type(exc).__name__) from exc

        status_code = int(response.status_code)
        if status_code != 201:
            raise YandexUploadHttpError("stage2", status_code)
        return YandexDirectUploadTransferResult(status_code=status_code)


# ---------------------------------------------------------------------------
# Deprecated research compatibility surface.
# ---------------------------------------------------------------------------


class YandexUploadStage1Requester(Protocol):
    def post_upload_url(self, params: dict[str, str]) -> Any:
        """Return a decoded research stage-one response."""


def _safe_exception_kinds(exc: BaseException) -> str:
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


_STAGE1_TRANSPORTS = {"requests", "http2"}
_STAGE1_CLIENT_PROFILES = {"bare", "desktop"}
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"


class YandexOAuthStage1Requester:
    """Deprecated v0.10 research requester retained for tooling compatibility."""

    def __init__(
        self,
        *,
        base_url: str,
        oauth_token: str,
        timeout_seconds: float = 30.0,
        transport_mode: str = "requests",
        client_profile: str = "bare",
        trust_env: bool = True,
    ) -> None:
        self._base_url = self._validate_base_url(base_url)
        token = str(oauth_token or "").strip()
        if not token:
            raise YandexUploadProtocolError("Stage-one OAuth credential is empty.")
        self._oauth_token = token
        self._timeout_seconds = float(timeout_seconds)
        clean_transport = str(transport_mode or "").strip().lower()
        clean_profile = str(client_profile or "").strip().lower()
        if clean_transport not in _STAGE1_TRANSPORTS:
            raise YandexUploadProtocolError("Unsupported stage-one transport mode.")
        if clean_profile not in _STAGE1_CLIENT_PROFILES:
            raise YandexUploadProtocolError("Unsupported stage-one client profile.")
        self._transport_mode = clean_transport
        self._client_profile = clean_profile
        self._trust_env = bool(trust_env)

    @staticmethod
    def _validate_base_url(value: str) -> str:
        clean = str(value or "").strip().rstrip("/")
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed = any(host == item or host.endswith(f".{item}") for item in _ALLOWED_YANDEX_DOMAINS)
        if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise YandexUploadProtocolError("Stage-one research base URL is invalid.")
        return clean

    @property
    def sanitized_profile(self) -> dict[str, Any]:
        return {
            "transport": self._transport_mode,
            "clientProfile": self._client_profile,
            "trustEnv": self._trust_env,
            "desktopClientHeader": self._client_profile == "desktop",
        }

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Authorization": f"OAuth {self._oauth_token}"}
        if self._client_profile == "desktop":
            headers["X-Yandex-Music-Client"] = _DESKTOP_CLIENT_LABEL
        return headers

    def post_upload_url(self, params: dict[str, str]) -> Any:
        endpoint = f"{self._base_url}/loader/upload-url"
        try:
            if self._transport_mode == "http2":
                with httpx.Client(
                    http1=True,
                    http2=True,
                    trust_env=self._trust_env,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = client.post(endpoint, params=dict(params), headers=self._headers())
            elif self._trust_env:
                response = requests.post(
                    endpoint,
                    params=dict(params),
                    headers=self._headers(),
                    timeout=self._timeout_seconds,
                )
            else:
                with requests.Session() as session:
                    session.trust_env = False
                    response = session.post(
                        endpoint,
                        params=dict(params),
                        headers=self._headers(),
                        timeout=self._timeout_seconds,
                    )
        except (requests.RequestException, httpx.HTTPError) as exc:
            raise YandexUploadProtocolError(
                f"Research stage-one request failed ({_safe_exception_kinds(exc)})."
            ) from exc
        if not 200 <= int(response.status_code) <= 299:
            raise YandexUploadProtocolError(
                f"Research stage-one endpoint returned HTTP {int(response.status_code)}."
            )
        try:
            return response.json()
        except ValueError:
            text = str(getattr(response, "text", "") or "").strip()
            if text:
                return text
            raise YandexUploadProtocolError("Research stage-one response was empty.")


@dataclass(slots=True, frozen=True)
class YandexUploadSlot:
    upload_url: str
    response_shape: dict[str, Any]
    poll_url: str | None = None
    track_id: str | None = None


@dataclass(slots=True, frozen=True)
class YandexUploadTransferResult:
    status_code: int
    response_shape: dict[str, Any]
    track_id: str | None = None


class YandexUploadTransport:
    """Deprecated fail-closed research transport retained for v0.10 tooling."""

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
        return self._stage1_requester is not None

    @property
    def stage1_profile(self) -> dict[str, Any] | None:
        if self._stage1_requester is None:
            return None
        value = getattr(self._stage1_requester, "sanitized_profile", None)
        return dict(value) if isinstance(value, dict) else None

    def require_stage1_profile(self) -> None:
        if self._stage1_requester is None:
            raise YandexUploadStage1UnavailableError(
                "Deprecated experimental Yandex upload is disabled; no request was sent."
            )

    @staticmethod
    def _shape(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {"type": "object", "keys": {str(key): YandexUploadTransport._shape(item) for key, item in value.items() if str(key).lower() not in {"token", "secret", "authorization", "cookie"}}}
        if isinstance(value, list):
            return {"type": "array", "length": len(value)}
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
            if isinstance(candidate, str):
                parsed = urlparse(candidate.strip())
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    return candidate.strip()
        return None

    @classmethod
    def _extract_upload_url(cls, payload: Any) -> str:
        value = cls._extract_http_url(payload, ("post-target", "postTarget", "url"))
        if not value:
            raise YandexUploadProtocolError("Research response has no upload URL.")
        return value

    @staticmethod
    def _extract_track_id(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("ugc-track-id", "ugcTrackId", "trackId", "track_id", "id"):
            value = payload.get(key)
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
        params = {"uid": str(uid), "playlist-id": str(playlist_id), "path": str(path).strip()}
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
        params = self.build_prepare_params(uid=uid, playlist_id=playlist_id, path=path, visibility=visibility)
        self.require_stage1_profile()
        assert self._stage1_requester is not None
        payload = self._stage1_requester.post_upload_url(params)
        return YandexUploadSlot(
            upload_url=self._extract_upload_url(payload),
            response_shape=self._shape(payload),
            poll_url=self._extract_http_url(payload, ("poll-result", "pollResult")),
            track_id=self._extract_track_id(payload),
        )

    def upload_file(self, slot: YandexUploadSlot, file_path: Path) -> YandexUploadTransferResult:
        path = Path(file_path)
        if not path.is_file() or path.stat().st_size <= 0:
            raise YandexUploadProtocolError("Research upload file is missing or empty.")
        try:
            with path.open("rb") as stream:
                response = requests.post(
                    slot.upload_url,
                    files={"file": (path.name, stream)},
                    timeout=self._transfer_timeout_seconds,
                )
        except requests.RequestException as exc:
            raise YandexUploadProtocolError(
                f"Research stage-two request failed ({_safe_exception_kinds(exc)})."
            ) from exc
        if not 200 <= int(response.status_code) <= 299:
            raise YandexUploadProtocolError(
                f"Research stage-two endpoint returned HTTP {int(response.status_code)}."
            )
        return YandexUploadTransferResult(
            status_code=int(response.status_code),
            response_shape={"type": "uninspected"},
        )
