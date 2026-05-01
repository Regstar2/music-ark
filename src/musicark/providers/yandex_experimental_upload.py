"""Experimental Yandex upload probe and placeholder (v0.11)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from musicark.core.config import load_config
from musicark.providers.yandex_music_provider import YandexMusicError, YandexMusicProvider
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository

from .yandex_upload_mapping import build_upload_replacement_mapping

_LIB_NAME = "yandex-music"


def client_exposes_upload_api() -> tuple[bool, list[str]]:
    """Heuristic: scan public Client methods for upload/import hooks (may be empty for 3.0.0)."""
    try:
        from yandex_music import Client  # type: ignore[attr-defined]
    except ImportError:
        return False, [f"{_LIB_NAME} package not installed"]

    names = [n.lower() for n in dir(Client) if not n.startswith("_")]
    hints = [n for n in names if "upload" in n or "import" in n or ("track" in n and "local" in n)]
    return len(hints) > 0, hints


def run_experimental_yandex_upload(
    *,
    database_path: Path,
    base_dir: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Single-file experimental upload: currently always not_supported (library has no upload surface)."""
    cfg = load_config(base_dir)
    if not cfg.experimental_yandex_upload:
        raise YandexMusicError(
            "experimental_yandex_upload is disabled in settings. "
            "Enable it under Settings (UI) or set MUSICARK_EXPERIMENTAL_YANDEX_UPLOAD=1."
        )
    if payload.get("confirm") is not True:
        raise YandexMusicError('Payload must include "confirm": true for any upload attempt.')

    try:
        lf_id = int(payload["local_file_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise YandexMusicError("local_file_id must be an integer.") from exc

    original_external_id = str(payload.get("original_external_id", "")).strip()
    if not original_external_id:
        raise YandexMusicError("original_external_id (Yandex catalogue id) is required.")

    audit = AuditLogRepository(database_path)
    storage = LocalLibraryStorageRepository(database_path)
    row = storage.fetch_local_audio_file_row_by_id(lf_id)
    if row is None:
        raise YandexMusicError(f"Unknown local_file_id={lf_id}.")
    local_path = Path(row["path"])
    if not local_path.is_file():
        raise YandexMusicError(f"Local audio file missing on disk: {local_path}")

    has_api, hint_names = client_exposes_upload_api()
    provider = YandexMusicProvider(base_dir=base_dir)
    provider.auth_check()

    outcome: dict[str, Any]
    status: str
    if not has_api:
        status = "not_supported"
        outcome = {
            "status": status,
            "library": _LIB_NAME,
            "upload_methods_found": hint_names,
            "mapping": build_upload_replacement_mapping(
                original_external_id=original_external_id,
                local_file_id=lf_id,
                uploaded_external_id=None,
                upload_status=status,
                detail="MarshalX yandex-music Client exposes no upload/import entry points in this version.",
            ),
        }
    else:
        # Future: invoke real upload API when library adds it and we add an integration test.
        status = "not_implemented"
        outcome = {
            "status": status,
            "library": _LIB_NAME,
            "upload_methods_found": hint_names,
            "mapping": build_upload_replacement_mapping(
                original_external_id=original_external_id,
                local_file_id=lf_id,
                uploaded_external_id=None,
                upload_status=status,
                detail="Upload hooks detected but execution is not implemented yet.",
            ),
        }

    audit.append(
        AuditEvent(
            event_type="experimental_yandex_upload_attempt",
            entity_type="local_audio_file",
            entity_id=str(lf_id),
            status=outcome["status"],
            details=json.dumps(
                {
                    "original_external_id": original_external_id,
                    "local_path": str(local_path.resolve()),
                    "payload": outcome,
                },
                ensure_ascii=False,
            )[:20000],
        )
    )
    return outcome
