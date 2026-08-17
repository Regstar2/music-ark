"""Format-adapter boundary for local metadata editing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class MetadataFormatError(RuntimeError):
    """Raised when an explicit metadata edit cannot be completed safely."""


class MetadataFormatAdapter(ABC):
    """Read/write one metadata format without owning filesystem transactions."""

    extensions: frozenset[str] = frozenset()

    def supports(self, path: Path) -> bool:
        return path.suffix.casefold() in self.extensions

    @abstractmethod
    def read(self, path: Path) -> dict[str, Any]:
        """Return basic fields plus real format-native text tags."""

    @abstractmethod
    def apply(
        self,
        path: Path,
        changes: dict[str, Any],
        *,
        artwork_data: bytes | None = None,
        artwork_mime: str | None = None,
        remove_artwork: bool = False,
        provenance: dict[str, str | None] | None = None,
    ) -> None:
        """Apply only requested changes to an already-created temporary copy."""

    @abstractmethod
    def artwork(self, path: Path) -> tuple[bytes, str] | None:
        """Return embedded front artwork, if present."""

    @abstractmethod
    def validate_audio(self, path: Path) -> float | None:
        """Validate the audio stream and return duration when available."""
