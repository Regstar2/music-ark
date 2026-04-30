"""Download provider contract and local import provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
import shutil
from pathlib import Path

from musicark.core.errors import MusicArkError
from musicark.providers.local_library import build_local_audio_file
from musicark.providers.models import LocalAudioFile

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
