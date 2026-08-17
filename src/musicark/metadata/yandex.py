"""Explicit Yandex metadata lookup kept behind the backend/provider boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from musicark.credentials import CredentialStore, SystemCredentialStore
from musicark.download.metadata import (
    Artwork,
    YandexTrackMetadata,
    metadata_from_yandex_track,
    sanitize_yandex_raw_data,
    yandex_artwork_url,
)
from musicark.providers.yandex_music_provider import YandexMusicError, YandexMusicProvider

from .artwork import ArtworkCache


_MAX_ARTWORK_BYTES = 8 * 1024 * 1024


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _raw_label(metadata: YandexTrackMetadata) -> str | None:
    raw = metadata.raw_data
    albums = raw.get("albums") if isinstance(raw, dict) else None
    album = albums[0] if isinstance(albums, list) and albums and isinstance(albums[0], dict) else {}
    candidates = [raw.get("label") if isinstance(raw, dict) else None, album.get("label")]
    labels = album.get("labels")
    if isinstance(labels, list) and labels:
        candidates.append(labels[0])
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, dict):
            value = _text(item.get("name") or item.get("title"))
            if value:
                return value
    return None


def _major(metadata: YandexTrackMetadata) -> str | None:
    raw = metadata.raw_data
    value = raw.get("major") if isinstance(raw, dict) else None
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("id"))
    return _text(value)


def metadata_fields(metadata: YandexTrackMetadata) -> dict[str, Any]:
    """Map only values actually present in Yandex's full Track DTO."""
    return {
        "title": metadata.title,
        "subtitle": metadata.subtitle,
        "version": metadata.version,
        "artists": list(metadata.artists),
        "album": metadata.album_title,
        "albumArtists": list(metadata.album_artists),
        "trackNumber": metadata.track_number,
        "totalTracks": metadata.total_tracks,
        "discNumber": metadata.disc_number,
        "totalDiscs": metadata.total_discs,
        "releaseDate": metadata.release_date,
        "year": metadata.release_year,
        "genres": [metadata.genre] if metadata.genre else [],
        "isrc": metadata.isrc,
        "publisher": metadata.publisher,
        "label": _raw_label(metadata),
        "copyright": metadata.copyright,
        "explicit": metadata.explicit,
        "durationSeconds": metadata.duration_seconds,
        "major": _major(metadata),
    }


def identity_fields(metadata: YandexTrackMetadata) -> dict[str, Any]:
    return {
        "providerId": "yandex_music",
        "externalId": metadata.external_id,
        "trackId": metadata.external_id,
        "realId": metadata.real_id,
        "albumId": metadata.album_id,
        "artistIds": list(metadata.artist_ids),
        "albumArtistIds": list(metadata.album_artist_ids),
    }


class YandexMetadataGateway:
    """Search/full Track lookup without exposing credentials or media URLs to Flutter."""

    def __init__(
        self,
        base_dir: Path | None,
        database_path: Path,
        *,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._credentials = credential_store or SystemCredentialStore()
        self._artwork = ArtworkCache(database_path, base_dir)

    def _provider(self) -> YandexMusicProvider:
        token = self._credentials.get_token()
        if not token:
            # Let the provider normalize the public missing-token error category.
            return YandexMusicProvider(base_dir=self._base_dir)
        return YandexMusicProvider(base_dir=self._base_dir, token=token)

    def _client(self):  # type: ignore[no-untyped-def]
        # YandexMusicProvider owns auth/client construction. Search is a v8.2.0
        # provider-side capability layered over that same authenticated boundary.
        return self._provider()._build_client()  # noqa: SLF001

    @staticmethod
    def _dto(value: Any) -> dict[str, Any]:
        return YandexMusicProvider._dto_payload(value)  # noqa: SLF001

    def search(self, query: str, *, limit: int = 20) -> list[YandexTrackMetadata]:
        clean = str(query).strip()
        if not clean:
            return []
        client = self._client()
        try:
            result = client.search(clean, type_="track")
            track_container = getattr(result, "tracks", None)
            short = list(getattr(track_container, "results", None) or [])[: max(1, min(int(limit), 50))]
            ids: list[str] = []
            fallback: dict[str, Any] = {}
            for item in short:
                payload = self._dto(item)
                identity = _text(payload.get("id") or getattr(item, "id", None))
                if identity and identity not in ids:
                    ids.append(identity)
                    fallback[identity] = item
            if not ids:
                return []
            full = list(client.tracks(ids) or [])
            by_id = {
                str(self._dto(item).get("id")): item
                for item in full
                if self._dto(item).get("id") is not None
            }
            return [
                metadata_from_yandex_track(by_id.get(identity, fallback[identity]), fallback_external_id=identity)
                for identity in ids
            ]
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, YandexMusicError):
                raise
            raise YandexMusicError("Failed to search Yandex Music tracks.") from exc

    def get(self, external_id: str) -> YandexTrackMetadata:
        identity = str(external_id).strip()
        if not identity:
            raise ValueError("Yandex Track ID is required.")
        client = self._client()
        try:
            tracks = list(client.tracks([identity]) or [])
        except Exception as exc:  # noqa: BLE001
            raise YandexMusicError(f"Failed to load Yandex track '{identity}'.") from exc
        if not tracks:
            raise YandexMusicError(f"Yandex track '{identity}' was not found.")
        return metadata_from_yandex_track(tracks[0], fallback_external_id=identity)

    def fetch_artwork(self, metadata: YandexTrackMetadata, *, size: str = "1000x1000") -> Artwork | None:
        url = yandex_artwork_url(metadata, size=size)
        if not url:
            return None
        try:
            response = requests.get(url, timeout=20, stream=True)
            response.raise_for_status()
            mime = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
            if not mime.startswith("image/"):
                return None
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _MAX_ARTWORK_BYTES:
                    return None
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data:
                return None
            self._artwork.cache_yandex(metadata.external_id, data, mime)
            return Artwork(data=data, mime=mime)
        except requests.RequestException:
            return None

    def public_payload(self, metadata: YandexTrackMetadata, *, cache_artwork: bool = False) -> dict[str, Any]:
        artwork_path = self._artwork.yandex_cached(metadata.external_id)
        if cache_artwork and artwork_path is None:
            artwork = self.fetch_artwork(metadata, size="400x400")
            if artwork is not None:
                artwork_path = self._artwork.yandex_cached(metadata.external_id)
        return {
            "fields": metadata_fields(metadata),
            "identity": identity_fields(metadata),
            "artwork": {"present": artwork_path is not None, "cachePath": artwork_path},
            # Raw provider data is sanitized and kept only for diagnostics/advanced compare.
            # It contains no auth headers, cookies, direct links, or signed URLs.
            "raw": sanitize_yandex_raw_data(metadata.raw_data),
        }
