"""Fail-closed compatibility boundary for the obsolete Yandex upload experiment.

v0.10.0 records Yandex Upload feasibility as BLOCKED.  There is no verified
provider upload protocol in MusicArk, so this module must never construct or
send an upload request.  The legacy developer CLI entry point is retained only
to fail safely for anyone who still has an old command/script.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from musicark.providers.yandex_music_provider import YandexMusicError


_BLOCKED_MESSAGE = (
    "Yandex Upload feasibility is BLOCKED in MusicArk v0.10.0: no verified "
    "upload protocol is implemented. No Yandex upload request was sent."
)


def client_exposes_upload_api() -> tuple[bool, list[str]]:
    """Return the conservative v0.10.0 feasibility result without network I/O."""
    return False, []


def run_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed; v0.10.0 has no reproducible upload protocol."""
    del database_path, base_dir, payload
    raise YandexMusicError(_BLOCKED_MESSAGE)
