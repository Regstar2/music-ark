"""Download provider contract and local import provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os
import re
import shutil
from pathlib import Path
import requests

from musicark.core.errors import MusicArkError
from musicark.providers.local_library import build_local_audio_file
from musicark.providers.models import LocalAudioFile
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)

from .models import DownloadTask


class DownloadProviderError(MusicArkError):
    """Raised when download provider fails to process a task."""


class DownloadProvider(ABC):
    """Abstraction for all file acquisition backends."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable provider identifier."""

    @abstractmethod
    def execute(self, task: DownloadTask) -> LocalAudioFile:
        """Execute task and return resulting local file metadata."""


class LocalImportProvider(DownloadProvider):
    """Provider that imports existing local files via download-system."""

    @property
    def provider_id(self) -> str:
        return "local_import"

    def execute(self, task: DownloadTask) -> LocalAudioFile:
        source_path = Path(task.source_id)
        target_folder = Path(task.target_folder)
        if not source_path.exists() or not source_path.is_file():
            raise DownloadProviderError(f"Import source '{source_path}' does not exist.")
        target_folder.mkdir(parents=True, exist_ok=True)
        target_path = target_folder / source_path.name
        if source_path.resolve() != target_path.resolve():
            shutil.copy2(source_path, target_path)
        return build_local_audio_file(target_path)


class YandexMusicDownloadProvider(DownloadProvider):
    """Download backend for Yandex track acquisition via download-system."""

    def __init__(self, base_dir: Path | None = None, token: str | None = None) -> None:
        self._base_dir = base_dir
        self._token = token.strip() if token else None

    @property
    def provider_id(self) -> str:
        return "yandex_music_download"

    def execute(self, task: DownloadTask) -> LocalAudioFile:
        track_id = self._extract_track_id(task)
        if not track_id.isdigit():
            raise DownloadProviderError(f"Invalid Yandex track id '{track_id}'.")
        target_folder = Path(task.target_folder)
        target_folder.mkdir(parents=True, exist_ok=True)
        quality = str(task.raw_payload.get("quality", "best")).lower() if task.raw_payload else "best"

        filename = f"yandex_{track_id}.mp3"
        destination = target_folder / filename
        if destination.exists() and destination.is_file() and destination.stat().st_size > 0:
            return build_local_audio_file(destination)

        direct_link = self._resolve_direct_link(track_id, quality=quality)
        self._download_to_file(direct_link, destination)
        return build_local_audio_file(destination)

    def _extract_track_id(self, task: DownloadTask) -> str:
        if task.raw_payload and task.raw_payload.get("track_id"):
            return str(task.raw_payload["track_id"])
        source = str(task.source_id)
        if "/" in source:
            tail = source.rstrip("/").split("/")[-1]
            if tail:
                return tail
        if source:
            return source
        match = re.search(r"\d+", source)
        if match:
            return match.group(0)
        raise DownloadProviderError(f"Cannot resolve Yandex track id from source '{source}'.")

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

    def _resolve_direct_link(self, track_id: str, quality: str = "best") -> str:
        client = self._build_client()
        try:
            tracks = client.tracks([track_id]) or []
            if not tracks:
                raise DownloadProviderError(f"Track '{track_id}' is not found.")
            track = tracks[0]
            infos = track.get_download_info(get_direct_links=True) or []
            if not infos:
                raise DownloadProviderError(f"Track '{track_id}' has no download info.")

            selected = infos[0]
            if quality == "best":
                selected = max(infos, key=lambda item: getattr(item, "bitrate_in_kbps", 0))
            elif quality.isdigit():
                target = int(quality)
                nearest = sorted(
                    infos,
                    key=lambda item: abs(getattr(item, "bitrate_in_kbps", 0) - target),
                )
                selected = nearest[0]

            link = getattr(selected, "direct_link", None)
            if not link:
                raise DownloadProviderError(f"Track '{track_id}' has no direct link.")
            return str(link)
        except DownloadProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DownloadProviderError(f"Failed to resolve download link for track '{track_id}'.") from exc

    def _download_to_file(self, direct_link: str, destination: Path) -> None:
        temporary = destination.with_name(destination.name + ".part")
        try:
            temporary.unlink(missing_ok=True)
            response = requests.get(direct_link, timeout=60, stream=True)
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        output.write(chunk)
            if not temporary.is_file() or temporary.stat().st_size <= 0:
                raise DownloadProviderError(f"Downloaded track is empty: '{destination}'.")
            temporary.replace(destination)
        except Exception as exc:  # noqa: BLE001
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, DownloadProviderError):
                raise
            raise DownloadProviderError(f"Failed to download track into '{destination}'.") from exc
