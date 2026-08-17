"""Download provider contracts and supported file acquisition backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable

import requests

from musicark.core.errors import MusicArkError
from musicark.provenance import trusted_yandex_origin
from musicark.providers.local_library import build_local_audio_file
from musicark.providers.models import LocalAudioFile
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)

from .metadata import (
    Artwork,
    AudioMetadataWriter,
    MetadataWriteError,
    YandexTrackMetadata,
    metadata_from_yandex_track,
    yandex_artwork_url,
)
from .models import DownloadTask


ProgressCallback = Callable[[int, int | None], None]
CancelCheck = Callable[[], bool]
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID_WINDOWS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_ARTWORK_BYTES = 5 * 1024 * 1024


class DownloadProviderError(MusicArkError):
    """Provider failure with a stable public error category."""

    def __init__(self, message: str, *, code: str = "provider_error") -> None:
        super().__init__(message)
        self.code = code


class DownloadCancelledError(DownloadProviderError):
    def __init__(self) -> None:
        super().__init__("Download was cancelled.", code="cancelled")


def sanitize_filename(value: str, *, fallback: str = "track.mp3", max_length: int = 180) -> str:
    """Return a Windows-safe leaf filename; never returns a path."""
    leaf = Path(str(value)).name
    clean = _INVALID_WINDOWS.sub("_", leaf).strip().rstrip(". ")
    if not clean:
        clean = fallback
    stem = Path(clean).stem.rstrip(". ") or "track"
    suffix = Path(clean).suffix
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
    room = max(16, max_length - len(suffix))
    stem = stem[:room].rstrip(". ") or "track"
    return f"{stem}{suffix}"[:max_length]


def yandex_download_filename(artists: list[str] | tuple[str, ...], title: str, track_id: str) -> str:
    artist = ", ".join(str(item).strip() for item in artists if str(item).strip()) or "Unknown Artist"
    track_title = str(title).strip() or "Unknown Track"
    return sanitize_filename(f"{artist} - {track_title} [yandex_{track_id}].mp3")


class DownloadProvider(ABC):
    """Abstraction for all file acquisition backends."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable provider identifier."""

    @abstractmethod
    def execute(self, task: DownloadTask) -> LocalAudioFile:
        """Execute a task using the legacy no-progress contract."""

    def execute_with_context(
        self,
        task: DownloadTask,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> LocalAudioFile:
        """Execute with optional progress/cancellation; legacy providers remain usable."""
        if cancelled is not None and cancelled():
            raise DownloadCancelledError()
        result = self.execute(task)
        if progress is not None:
            progress(int(result.file_size), int(result.file_size))
        return result


class LocalImportProvider(DownloadProvider):
    """Provider that imports existing local files via download-system."""

    @property
    def provider_id(self) -> str:
        return "local_import"

    def execute(self, task: DownloadTask) -> LocalAudioFile:
        source_path = Path(task.source_id)
        target_folder = Path(task.target_folder)
        if not source_path.exists() or not source_path.is_file():
            raise DownloadProviderError(
                f"Import source '{source_path}' does not exist.", code="source_missing"
            )
        target_folder.mkdir(parents=True, exist_ok=True)
        target_path = target_folder / sanitize_filename(source_path.name, fallback="imported-audio")
        if source_path.resolve() != target_path.resolve():
            shutil.copy2(source_path, target_path)
        return build_local_audio_file(target_path)


class YandexMusicDownloadProvider(DownloadProvider):
    """Authorized Yandex Music track acquisition backend."""

    def __init__(self, base_dir: Path | None = None, token: str | None = None) -> None:
        self._base_dir = base_dir
        self._token = token.strip() if token else None
        self._metadata_writer = AudioMetadataWriter()

    @property
    def provider_id(self) -> str:
        return "yandex_music_download"

    def execute(self, task: DownloadTask) -> LocalAudioFile:
        # Preserve the v0.7 no-context contract for reference tools/tests. The
        # production DownloadService always calls execute_with_context().
        return self._execute_legacy(task)

    def execute_with_context(
        self,
        task: DownloadTask,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> LocalAudioFile:
        if progress is None and cancelled is None:
            return self._execute_legacy(task)
        return self._execute_rich(
            task,
            progress=progress,
            cancelled=cancelled,
        )

    def _execute_legacy(self, task: DownloadTask) -> LocalAudioFile:
        track_id = self._validated_track_id(task)
        quality = str(task.raw_payload.get("quality", "best")).lower() if task.raw_payload else "best"
        destination = self._destination(task, track_id)
        if destination.exists():
            if destination.is_file() and destination.stat().st_size > 0 and self._is_valid_existing_audio(destination):
                return build_local_audio_file(destination)
            destination = self._collision_safe_destination(destination)
        direct_link = self._resolve_direct_link(track_id, quality=quality)
        self._download_to_file(direct_link, destination)
        return build_local_audio_file(destination)

    def _execute_rich(
        self,
        task: DownloadTask,
        *,
        progress: ProgressCallback | None,
        cancelled: CancelCheck | None,
    ) -> LocalAudioFile:
        track_id = self._validated_track_id(task)
        quality = str(task.raw_payload.get("quality", "best")).lower() if task.raw_payload else "best"
        destination = self._destination(task, track_id)
        if destination.exists():
            if (
                destination.is_file()
                and destination.stat().st_size > 0
                and self._is_valid_existing_audio(destination)
                and self._has_trusted_yandex_origin(destination, track_id)
            ):
                if progress is not None:
                    size = int(destination.stat().st_size)
                    progress(size, size)
                return build_local_audio_file(destination)
            destination = self._collision_safe_destination(destination)

        track, direct_link = self._resolve_track_and_link(track_id, quality=quality)
        metadata = metadata_from_yandex_track(track, fallback_external_id=track_id).with_fallback(
            task.raw_payload or {}
        )
        temporary = destination.with_name(destination.name + ".part")
        try:
            self._download_to_part(
                direct_link,
                temporary,
                progress=progress,
                cancelled=cancelled,
            )
            self._metadata_writer.validate_audio(temporary)
            artwork = self._fetch_artwork(metadata)
            self._metadata_writer.write_mp3(temporary, metadata, artwork=artwork)
            self._metadata_writer.validate_audio(temporary)
            temporary.replace(destination)
            return build_local_audio_file(destination)
        except Exception as exc:  # noqa: BLE001
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, DownloadProviderError):
                raise
            if isinstance(exc, MetadataWriteError):
                raise DownloadProviderError(str(exc), code="metadata_write") from exc
            raise

    def _validated_track_id(self, task: DownloadTask) -> str:
        track_id = self._extract_track_id(task)
        if not track_id.isdigit():
            raise DownloadProviderError(f"Invalid Yandex track id '{track_id}'.", code="invalid_track_id")
        return track_id

    def _destination(self, task: DownloadTask, track_id: str) -> Path:
        target_folder = Path(task.target_folder).expanduser().resolve(strict=False)
        try:
            target_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DownloadProviderError(
                f"Cannot create download folder '{target_folder}'.", code="write_permission"
            ) from exc
        requested = str(task.raw_payload.get("target_filename") or f"yandex_{track_id}.mp3")
        filename = sanitize_filename(requested, fallback=f"yandex_{track_id}.mp3")
        destination = (target_folder / filename).resolve(strict=False)
        if destination.parent != target_folder:
            raise DownloadProviderError("Download destination escapes the selected root.", code="unsafe_path")
        return destination

    @staticmethod
    def _is_valid_existing_audio(path: Path) -> bool:
        try:
            from mutagen import File as MutagenFile  # type: ignore

            audio = MutagenFile(str(path), easy=True)
            return audio is not None and getattr(audio, "info", None) is not None
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _has_trusted_yandex_origin(path: Path, track_id: str) -> bool:
        try:
            from mutagen.id3 import ID3

            tags = ID3(str(path))
            values: dict[str, str] = {}
            for frame in tags.getall("TXXX"):
                description = str(getattr(frame, "desc", ""))
                text = getattr(frame, "text", ())
                if description and text:
                    values[description] = str(text[0]).strip()
            provider_id, external_id = trusted_yandex_origin(values)
            return provider_id == "yandex_music" and external_id == track_id
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _collision_safe_destination(destination: Path) -> Path:
        for index in range(2, 10_000):
            candidate = destination.with_name(f"{destination.stem} ({index}){destination.suffix}")
            if not candidate.exists():
                return candidate
        raise DownloadProviderError(
            f"Cannot find a free filename near '{destination.name}'.", code="file_collision"
        )

    def _extract_track_id(self, task: DownloadTask) -> str:
        if task.raw_payload and task.raw_payload.get("track_id"):
            return str(task.raw_payload["track_id"])
        source = str(task.source_id).strip()
        if "/" in source:
            tail = source.rstrip("/").split("/")[-1]
            if tail:
                return tail
        if source:
            return source
        raise DownloadProviderError("Cannot resolve Yandex track id.", code="invalid_track_id")

    def _resolve_token(self) -> str:
        if self._token:
            return self._token
        token = os.getenv("YANDEX_MUSIC_TOKEN", "").strip()
        if token:
            return token
        if self._base_dir is not None:
            local_properties = self._base_dir / "local.properties"
            if local_properties.exists():
                for line in local_properties.read_text(encoding="utf-8").splitlines():
                    if line.startswith("YANDEX_MUSIC_TOKEN="):
                        local_token = line.split("=", 1)[1].strip()
                        if local_token:
                            return local_token
        raise YandexTokenMissingError("YANDEX_MUSIC_TOKEN is not configured.")

    def _build_client(self):  # type: ignore[no-untyped-def]
        token = self._resolve_token()
        try:
            from yandex_music import Client  # type: ignore
        except ImportError as exc:
            raise YandexMusicError(
                "yandex-music dependency is missing. Install requirements-yandex.txt."
            ) from exc
        try:
            return Client(token).init()
        except Exception as exc:  # noqa: BLE001
            raise YandexAuthenticationError("Failed to initialize Yandex client for download.") from exc

    @staticmethod
    def _select_download_info(infos: list[Any], quality: str) -> Any:
        mp3_infos = [item for item in infos if str(getattr(item, "codec", "")).lower() == "mp3"]
        candidates = mp3_infos or list(infos)
        selected = candidates[0]
        if quality == "best":
            selected = max(candidates, key=lambda item: getattr(item, "bitrate_in_kbps", 0))
        elif quality.isdigit():
            target = int(quality)
            selected = min(
                candidates,
                key=lambda item: abs(getattr(item, "bitrate_in_kbps", 0) - target),
            )
        return selected

    def _resolve_track_and_link(self, track_id: str, quality: str = "best") -> tuple[Any, str]:
        client = self._build_client()
        try:
            tracks = client.tracks([track_id]) or []
            if not tracks:
                raise DownloadProviderError(f"Track '{track_id}' is unavailable.", code="track_unavailable")
            track = tracks[0]
            infos = track.get_download_info() or []
            if not infos:
                raise DownloadProviderError(
                    f"Track '{track_id}' has no download info.", code="no_download_info"
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
                    f"Track '{track_id}' has no direct link.", code="no_download_info"
                )
            return track, str(link)
        except (DownloadProviderError, YandexAuthenticationError, YandexTokenMissingError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise DownloadProviderError(
                f"Failed to resolve download information for track '{track_id}'.",
                code="provider_request",
            ) from exc

    def _resolve_direct_link(self, track_id: str, quality: str = "best") -> str:
        _track, link = self._resolve_track_and_link(track_id, quality=quality)
        return link

    def _fetch_artwork(self, metadata: YandexTrackMetadata) -> Artwork | None:
        url = yandex_artwork_url(metadata)
        if not url:
            return None
        try:
            response = requests.get(url, timeout=20, stream=True)
            response.raise_for_status()
            mime = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if not mime.startswith("image/"):
                return None
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > _MAX_ARTWORK_BYTES:
                    return None
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data:
                return None
            return Artwork(data=data, mime=mime)
        except requests.RequestException:
            return None

    def _download_to_part(
        self,
        direct_link: str,
        temporary: Path,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> None:
        try:
            temporary.unlink(missing_ok=True)
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
                    f"Downloaded track is empty: '{temporary.name}'.", code="invalid_audio"
                )
        except Exception as exc:  # noqa: BLE001
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, DownloadProviderError):
                raise
            if isinstance(exc, requests.HTTPError):
                raise DownloadProviderError("Yandex download returned an HTTP error.", code="http_error") from exc
            if isinstance(exc, requests.RequestException):
                raise DownloadProviderError("Network error while downloading track.", code="network_error") from exc
            if isinstance(exc, OSError):
                raise DownloadProviderError("Cannot write the downloaded audio file.", code="disk_file_error") from exc
            raise DownloadProviderError("Failed to download track.", code="provider_error") from exc

    def _download_to_file(
        self,
        direct_link: str,
        destination: Path,
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCheck | None = None,
    ) -> None:
        temporary = destination.with_name(destination.name + ".part")
        self._download_to_part(
            direct_link,
            temporary,
            progress=progress,
            cancelled=cancelled,
        )
        try:
            temporary.replace(destination)
        except Exception as exc:  # noqa: BLE001
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, OSError):
                raise DownloadProviderError("Cannot write the downloaded audio file.", code="disk_file_error") from exc
            raise
