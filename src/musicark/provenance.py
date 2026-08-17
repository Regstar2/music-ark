"""Stable machine-readable provenance tags written into MusicArk-managed audio files."""

from __future__ import annotations

MUSICARK_METADATA_SCHEMA_VERSION = "1"
MUSICARK_PROVIDER = "MUSICARK_PROVIDER"
MUSICARK_EXTERNAL_ID = "MUSICARK_EXTERNAL_ID"
MUSICARK_METADATA_SCHEMA = "MUSICARK_METADATA_SCHEMA"
YANDEX_TRACK_ID = "YANDEX_TRACK_ID"
YANDEX_REAL_ID = "YANDEX_REAL_ID"
YANDEX_ALBUM_ID = "YANDEX_ALBUM_ID"
YANDEX_ARTIST_IDS = "YANDEX_ARTIST_IDS"

PROVENANCE_DESCRIPTIONS = frozenset(
    {
        MUSICARK_PROVIDER,
        MUSICARK_EXTERNAL_ID,
        MUSICARK_METADATA_SCHEMA,
        YANDEX_TRACK_ID,
        YANDEX_REAL_ID,
        YANDEX_ALBUM_ID,
        YANDEX_ARTIST_IDS,
    }
)


def trusted_yandex_origin(values: dict[str, str]) -> tuple[str | None, str | None]:
    """Return exact provider identity only for a complete MusicArk provenance set."""
    provider = str(values.get(MUSICARK_PROVIDER) or "").strip()
    external_id = str(values.get(MUSICARK_EXTERNAL_ID) or "").strip()
    schema = str(values.get(MUSICARK_METADATA_SCHEMA) or "").strip()
    yandex_track_id = str(values.get(YANDEX_TRACK_ID) or "").strip()
    if (
        provider == "yandex_music"
        and external_id
        and schema == MUSICARK_METADATA_SCHEMA_VERSION
        and yandex_track_id == external_id
    ):
        return provider, external_id
    return None, None
