"""Fail-closed compatibility boundary for the obsolete Yandex upload experiment.

v0.10.0 feasibility is complete and v0.11.0 provides a separate production
single-track upload service. This legacy module remains intentionally disabled
so old commands/scripts cannot silently turn into a real upload mutation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.providers.yandex_music_provider import YandexMusicError


_BLOCKED_MESSAGE = (
    "BLOCKED legacy experimental_yandex_upload action: this deprecated compatibility "
    "entry point is intentionally disabled. Use the explicit v0.11.0 "
    "yandex_upload_track production workflow instead. No Yandex upload request was sent."
)


def client_exposes_upload_api() -> tuple[bool, list[str]]:
    """Return the legacy fail-closed compatibility result without network I/O."""
    return False, []


def run_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed so legacy callers cannot perform the production mutation."""
    del database_path, base_dir, payload
    raise YandexMusicError(_BLOCKED_MESSAGE)
