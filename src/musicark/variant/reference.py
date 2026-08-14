"""Resolve trusted local reference audio for a provider track identity."""

from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import sqlite3

from .models import ReferenceAudio


_YANDEX_REFERENCE = re.compile(r"^yandex[_-](?P<id>\d+)$", re.IGNORECASE)
_AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".mp4", ".aac", ".ogg", ".opus", ".wav"})


def strict_yandex_id_from_path(path: Path) -> str | None:
    """Return an ID only for the exact historical yandex_<id>/yandex-<id> convention."""
    match = _YANDEX_REFERENCE.fullmatch(path.stem)
    return match.group("id") if match else None


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8", "surrogatepass")
    return sha256(payload).hexdigest()


class ReferenceAudioResolver:
    def __init__(self, database_path: Path, base_dir: Path | None = None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir

    def resolve(self, provider_id: str, external_id: str) -> ReferenceAudio | None:
        if provider_id != "yandex_music" or not str(external_id).isdigit():
            return None
        expected = str(external_id)

        # Prefer the app-managed download folder when present.
        root = (self._base_dir or self._database_path.parent.parent) / ".musicark" / "downloads" / "yandex"
        if root.is_dir():
            for prefix in ("yandex_", "yandex-"):
                for ext in sorted(_AUDIO_EXTENSIONS):
                    candidate = root / f"{prefix}{expected}{ext}"
                    if candidate.is_file():
                        return ReferenceAudio(candidate, provider_id, expected)

        # Also allow already indexed local files, but only the same strict filename convention.
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    "SELECT path FROM local_audio_files WHERE availability != 'missing' ORDER BY id"
                ).fetchall()
        except sqlite3.Error:
            return None
        for (raw_path,) in rows:
            path = Path(str(raw_path))
            if path.suffix.casefold() not in _AUDIO_EXTENSIONS:
                continue
            if strict_yandex_id_from_path(path) == expected and path.is_file():
                return ReferenceAudio(path, provider_id, expected)
        return None
