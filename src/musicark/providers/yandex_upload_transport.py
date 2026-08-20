"""Yandex Music UGC upload transports.

``YandexDirectUploadTransport`` is the production v0.11.0 transport. It follows
only the direct protocol verified by the v0.10.0 live Python proof: one fixed
stage-one request, one multipart stage-two request, no credentials on either
request and no automatic retry.

The older ``YandexUploadTransport`` and ``YandexOAuthStage1Requester`` symbols
remain unchanged as deprecated research compatibility boundaries. Production
code must not use them.
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
    """Raised when an upload protocol cannot be followed safely."""


class YandexUploadNetworkError(YandexUploadProtocolError):
    """Sanitized production transport failure that omits URL/error text."""

    def __init__(self, stage: str, exception_type: str) -> None:
        super().__init__(f"Yandex upload {stage} transport failed ({exception_type}).")
        self.stage = stage
        self.exception_type = exception_type


class YandexUploadHttpError(YandexUploadProtocolError):
    """Production HTTP status failure without response body or signed URL exposure."""

    def __init__(self, stage: str, status_code: int) -> None:
        super().__init__(f"Yandex upload {stage} returned HTTP {status_code}.")
        self.stage = stage
        self.status_code = int(status_code)


@dataclass(slots=True, frozen=True)
class YandexDirectUploadSlot:
    """Internal production stage-one response; signed URLs never cross the service boundary."""

    post_target: str
    poll_result: str | None
    ugc_track_id: str | None
    status_code: int


@dataclass(slots=True, frozen=True)
class YandexDirectUploadTransferResult:
    """Sanitized successful production stage-two response metadata."""

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
        """Perform exactly one credential-free production stage-one request."""
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
        """Perform exactly one multipart production stage-two POST without auth/session headers."""
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
# Deprecated v0.10 research compatibility surface. Keep behavior stable for
# research tooling and tests; production v0.11.0 uses only the direct classes
# above.
# ---------------------------------------------------------------------------


class YandexUploadStage1UnavailableError(YandexUploadProtocolError):
    """Raised when no verified research stage-one request profile is available."""


class YandexUploadStage1Requester(Protocol):
    """Injectable research stage-one boundary."""

    def post_upload_url(self, params: dict[str, str]) -> Any:
        """Return the decoded response from the recovered loader/upload-url request."""


def _safe_exception_kinds(exc: BaseException) -> str:
    """Return only exception class names from a transport failure tree."""
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
    """Deprecated OAuth requester retained only for v0.10 research compatibility."""

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
        if self._timeout_seconds <= 0:
            raise YandexUploadProtocolError("Stage-one timeout must be positive.")

        clean_transport = str(transport_mode or "").strip().lower()
        if clean_transport not in _STAGE1_TRANSPORTS:
            raise YandexUploadProtocolError("Unsupported stage-one transport mode.")
        self._transport_mode = clean_transport

        clean_profile = str(client_profile or "").strip().lower()
        if clean_profile not in _STAGE1_CLIENT_PROFILES:
            raise YandexUploadProtocolError("Unsupported stage-one client profile.")
        self._client_profile = clean_profile
        self._trust_env = bool(trust_env)

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

    @property
    def sanitized_profile(self) -> dict[str, Any]:
        """Return only public/non-secret research request-profile choices."""
        return {
            "transport": self._transport_mode,
            "clientProfile": self._client_profile,
            "trustEnv": self._trust_env,
            "desktopClientHeader": self._client_profile == "desktop",
        }

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"OAuth {self._oauth_token}",
        }
        if self._client_profile == "desktop":
            headers["X-Yandex-Music-Client"] = _DESKTOP_CLIENT_LABEL
        return headers

    def _profile_label(self) -> str:
        trust = "inherit" if self._trust_env else "ignore"
        return f"client={self._transport_mode},profile={self._client_profile},env={trust}"

    def _requests_post(self, endpoint: str, params: dict[str, str]) -> Any:
        kwargs = {
            "params": dict(params),
            "headers": self._headers(),
            "timeout": self._timeout_seconds,
        }
        if self._trust_env:
            return requests.post(endpoint, **kwargs)
        with requests.Session() as session:
            session.trust_env = False
            return session.post(endpoint, **kwargs)

    def _http2_post(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        with httpx.Client(
            http1=True,
            http2=True,
            trust_env=self._trust_env,
            timeout=self._timeout_seconds,
            follow_redirects=False,
        ) as client:
            return client.post(endpoint, params=dict(params), headers=self._headers())

    @staticmethod
    def _decode_response(response: Any) -> Any:
        status_code = int(response.status_code)
        if not 200 <= status_code <= 299:
            return None
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

    def post_upload_url(self, params: dict[str, str]) -> Any:
        endpoint = f"{self._base_url}/loader/upload-url"
        try:
            if self._transport_mode == "http2":
                response = self._http2_post(endpoint, params)
            else:
                response = self._requests_post(endpoint, params)
        except (requests.RequestException, httpx.HTTPError) as exc:
            kind = _safe_exception_kinds(exc)
            raise YandexUploadProtocolError(
                f"Yandex stage-one OAuth request failed ({self._profile_label()},transport={kind})."
            ) from exc

        status_code = int(response.status_code)
        http_version = str(getattr(response, "http_version", "") or "unknown")
        if not 200 <= status_code <= 299:
            version_suffix = f",httpVersion={http_version}" if self._transport_mode == "http2" else ""
            raise YandexUploadProtocolError(
                f"Yandex stage-one endpoint returned HTTP {status_code} ({self._profile_label()}{version_suffix})."
            )

        return self._decode_response(response)


@dataclass(slots=True, frozen=True)
class YandexUploadSlot:
    """Prepared server-side research upload slot returned by ``loader/upload-url``."""

    upload_url: str
    response_shape: dict[str, Any]
    poll_url: str | None = None
    track_id: str | None = None


@dataclass(slots=True, frozen=True)
class YandexUploadTransferResult:
    """Sanitized research result of sending one file to the prepared dynamic URL."""

    status_code: int
    response_shape: dict[str, Any]
    track_id: str | None = None


class YandexUploadTransport:
    """Deprecated v0.10 two-stage research transport with fail-closed stage one."""

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
        """Whether an explicitly verified research stage-one requester was supplied."""
        return self._stage1_requester is not None

    @property
    def stage1_profile(self) -> dict[str, Any] | None:
        """Expose only the requester's sanitized public profile metadata."""
        if self._stage1_requester is None:
            return None
        value = getattr(self._stage1_requester, "sanitized_profile", None)
        return dict(value) if isinstance(value, dict) else None

    def require_stage1_profile(self) -> None:
        """Preserve the v0.10 fail-closed research behavior."""
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
        """Build only the recovered research stage-one query contract."""
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
        """Request a dynamic URL only through the deprecated research requester."""
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
        """Preserve the deprecated research Stage 2 behavior for compatibility tests."""
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
