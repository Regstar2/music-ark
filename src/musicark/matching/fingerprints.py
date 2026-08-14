"""Stable fingerprints for matching inputs whose metadata affects decisions."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def provider_fingerprint(
    provider_id: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Hash only provider metadata that materially affects matching."""
    relevant = {
        "provider_id": provider_id,
        "external_id": external_id,
        "title": payload.get("title"),
        "artists": payload.get("artists") or [],
        "album_title": payload.get("album_title") or payload.get("album"),
        "duration_seconds": payload.get("duration_seconds"),
    }
    encoded = json.dumps(
        relevant,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def local_file_fingerprint(row: tuple[Any, ...]) -> str:
    """Hash material local-file metadata for one accepted manual link."""
    relevant = {
        "path": row[0],
        "file_size": row[1],
        "modified_ns": row[2],
        "title": row[3],
        "artists_json": row[4],
        "album": row[5],
        "duration_seconds": row[6],
        "codec": row[7],
    }
    encoded = json.dumps(
        relevant,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
