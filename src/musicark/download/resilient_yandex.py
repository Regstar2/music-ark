"""Resilient Yandex Music download provider for long user queue workers.

The legacy provider remains the compatibility baseline. This subclass keeps one
initialized Yandex client for the lifetime of a worker process, classifies
provider failures into stable public error codes, and retries only transient
network/provider failures with bounded exponential backoff.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import requests

from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)

from .models import DownloadTask
from .provider import (
    CancelCheck,
    DownloadCancelledError,
    DownloadProviderError,
    ProgressCallback,
    YandexMusicDownloadProvider,
)


Sleeper = Callable[[float], None]
_RETRYABLE_CODES = {
    "network_error",
    "provider_network",
    "provider_timeout",
    "provider_unavailable",
    "rate_limited",
}
_HTTP_STATUS_RE = re.compile(r"\((\d{3})\):")


class ResilientYandexMusicDownloadProvider(YandexMusicDownloadProvider):
    """Yandex download provider hardened for long sequential queue runs."""

    def __init__(
        self,
        *args: Any,
        retry_attempts: int = 3,
        sleeper: Sleeper = time.sleep,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if retry_attempts <= 0:
            raise ValueError("retry_attempts must be positive")
        self._retry_attempts = int(retry_attempts)
        self._sleeper = sleeper
        self._client: Any | None = None

    def _validated_track_id(self, task: DownloadTask) -> str:
        track_id = self._extract_track_id(task)
        if track_id.isdigit():
            return track_id
        try:
            UUID(track_id)
        except (ValueError, AttributeError):
            raise DownloadProviderError(
                f"Invalid Yandex track id '{track_id}'.",
                code="invalid_track_id",
            ) from None
        raise DownloadProviderError(
            "User-uploaded Yandex tracks are not available through the supported restore path.",
            code="ugc_unsupported",
        )

    @staticmethod
    def _safe_http_status(exc: BaseException) -> int | None:
        """Extract only an HTTP status from yandex-music's error text.

        yandex-music 3.0.0 can include response content in ``NetworkError``.
        The raw provider body is inspected only in memory and is never propagated
        into persisted/user-visible error details.
        """
        match = _HTTP_STATUS_RE.search(str(exc))
        if match is None:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _classified_yandex_error(self, exc: BaseException) -> Exception:
        try:
            from yandex_music.exceptions import (  # type: ignore
                BadRequestError,
                NetworkError,
                NotFoundError,
                TimedOutError,
                UnauthorizedError,
                YandexMusicError as LibraryYandexMusicError,
            )
        except ImportError:
            return DownloadProviderError(
                "Yandex Music request failed.",
                code="provider_request",
            )

        if isinstance(exc, UnauthorizedError):
            self._client = None
            return YandexAuthenticationError("Yandex Music authentication failed.")
        if isinstance(exc, NotFoundError):
            return DownloadProviderError(
                "Yandex Music track is unavailable.",
                code="track_unavailable",
            )
        if isinstance(exc, TimedOutError):
            return DownloadProviderError(
                "Yandex Music request timed out.",
                code="provider_timeout",
            )
        if isinstance(exc, BadRequestError):
            return DownloadProviderError(
                "Yandex Music rejected the track request.",
                code="provider_rejected",
            )
        if isinstance(exc, NetworkError):
            status = self._safe_http_status(exc)
            if status == 429:
                return DownloadProviderError(
                    "Yandex Music temporarily rate-limited the request (HTTP 429).",
                    code="rate_limited",
                )
            if status is not None and 500 <= status <= 599:
                return DownloadProviderError(
                    f"Yandex Music is temporarily unavailable (HTTP {status}).",
                    code="provider_unavailable",
                )
            return DownloadProviderError(
                "Yandex Music network request failed.",
                code="provider_network",
            )
        if isinstance(exc, LibraryYandexMusicError):
            return DownloadProviderError(
                f"Yandex Music request failed ({type(exc).__name__}).",
                code="provider_request",
            )
        return DownloadProviderError(
            f"Yandex Music request failed ({type(exc).__name__}).",
            code="provider_request",
        )

    def _build_client(self):  # type: ignore[no-untyped-def]
        if self._client is not None:
            return self._client
        token = self._resolve_token()
        try:
            from yandex_music import Client  # type: ignore
        except ImportError as exc:
            raise YandexMusicError(
                "yandex-music dependency is missing. Install requirements-yandex.txt."
            ) from exc
        try:
            client = Client(token).init()
        except Exception as exc:  # noqa: BLE001 - normalize provider errors without raw bodies.
            classified = self._classified_yandex_error(exc)
            raise classified from exc
        self._client = client
        return client

    def _retry(self, operation: Callable[[], Any]) -> Any:
        for attempt in range(1, self._retry_attempts + 1):
            try:
                return operation()
            except (YandexTokenMissingError, YandexAuthenticationError, DownloadCancelledError):
                raise
            except DownloadProviderError as exc:
                if exc.code not in _RETRYABLE_CODES or attempt >= self._retry_attempts:
                    raise
                self._sleeper(float(2 ** (attempt - 1)))
        raise DownloadProviderError("Yandex Music request failed.", code="provider_request")

    def _resolve_track_and_link_once(self, track_id: str, quality: str) -> tuple[Any, str]:
        client = self._build_client()
        try:
            tracks = client.tracks([track_id]) or []
            if not tracks:
                raise DownloadProviderError(
                    f"Track '{track_id}' is unavailable.",
                    code="track_unavailable",
                )
            track = tracks[0]
            infos = track.get_download_info() or []
            if not infos:
                raise DownloadProviderError(
                    f"Track '{track_id}' has no download info.",
                    code="no_download_info",
                )
            selected = self._select_download_info(list(infos), quality)
            get_direct_link = getattr(selected, "get_direct_link", None)
            if not callable(get_direct_link):
                raise DownloadProviderError(
                    f"Track '{track_id}' download info cannot resolve a direct link.",
                    code="no_download_info",
                )
            link = get_direct_link()
            if not link:
                raise DownloadProviderError(
                    f"Track '{track_id}' has no direct link.",
                    code="no_download_info",
                )
            return track, str(link)
        except (DownloadProviderError, YandexAuthenticationError, YandexTokenMissingError):
            raise
        except Exception as exc:  # noqa: BLE001 - normalize provider exceptions.
            classified = self._classified_yandex_error(exc)
            raise classified from exc

    def _resolve_track_and_link(self, track_id: str, quality: str = "best") -> tuple[Any, str]:
        return self._retry(lambda: self._resolve_track_and_link_once(track_id, quality))

    @staticmethod
    def _direct_http_error(exc: requests.HTTPError) -> DownloadProviderError:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        try:
            code = int(status) if status is not None else None
        except (TypeError, ValueError):
            code = None
        if code == 429:
            return DownloadProviderError(
                "Yandex download was rate-limited (HTTP 429).",
                code="rate_limited",
            )
        if code is not None and 500 <= code <= 599:
            return DownloadProviderError(
                f"Yandex download service is temporarily unavailable (HTTP {code}).",
                code="provider_unavailable",
            )
        return DownloadProviderError(
            f"Yandex download returned HTTP {code}."
            if code is not None
            else "Yandex download returned an HTTP error.",
            code="http_error",
        )

    def _download_to_part_once(
        self,
        direct_link: str,
        temporary: Path,
        *,
        progress: ProgressCallback | None,
        cancelled: CancelCheck | None,
    ) -> None:
        temporary.unlink(missing_ok=True)
        try:
            if cancelled is not None and cancelled():
                raise DownloadCancelledError()
            response = requests.get(direct_link, timeout=60, stream=True)
            response.raise_for_status()
            raw_total = response.headers.get("Content-Length")
            try:
                total = int(raw_total) if raw_total is not None and int(raw_total) >= 0 else None
            except (TypeError, ValueError):
                total = None
            downloaded = 0
            if progress is not None:
                progress(0, total)
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=65536):
                    if cancelled is not None and cancelled():
                        raise DownloadCancelledError()
                    if not chunk:
                        continue
                    output.write(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(downloaded, total)
            if not temporary.is_file() or temporary.stat().st_size <= 0:
                raise DownloadProviderError(
                    f"Downloaded track is empty: '{temporary.name}'.",
                    code="invalid_audio",
                )
        except Exception as exc:  # noqa: BLE001 - normalize and always remove partial files.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, DownloadProviderError):
                raise
            if isinstance(exc, requests.HTTPError):
                raise self._direct_http_error(exc) from exc
            if isinstance(exc, requests.Timeout):
                raise DownloadProviderError(
                    "Yandex download request timed out.",
                    code="provider_timeout",
                ) from exc
            if isinstance(exc, requests.RequestException):
                raise DownloadProviderError(
                    "Network error while downloading track.",
                    code="network_error",
                ) from exc
            if isinstance(exc, OSError):
                raise DownloadProviderError(
                    "Cannot write the downloaded audio file.",
                    code="disk_file_error",
                ) from exc
            raise DownloadProviderError("Failed to download track.", code="provider_request") from exc

    def _download_to_part(
        self,
        direct_link: str,
        temporary: Path,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> None:
        self._retry(
            lambda: self._download_to_part_once(
                direct_link,
                temporary,
                progress=progress,
                cancelled=cancelled,
            )
        )
