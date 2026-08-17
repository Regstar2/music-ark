"""Mapping utilities from Yandex payloads to universal provider models."""

from __future__ import annotations

from typing import Any

from .models import ProviderPlaylist, ProviderTrack, TrackSource


def _artwork_url(raw_track: dict, album: dict, *, size: str = "200x200") -> str | None:
    value = (
        raw_track.get("cover_uri")
        or raw_track.get("og_image")
        or album.get("cover_uri")
        or album.get("og_image")
    )
    if value is None:
        return None
    url = str(value).strip().replace("%%", size)
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if "://" not in url:
        return f"https://{url.lstrip('/')}"
    return url


def map_yandex_track(raw_track: dict) -> ProviderTrack:
    """Map normalized Yandex track payload into ProviderTrack."""
    track_id = str(raw_track.get("id", ""))
    artists_payload = raw_track.get("artists") or []
    artists = tuple(
        str(artist.get("name", "")).strip()
        for artist in artists_payload
        if isinstance(artist, dict) and artist.get("name")
    )
    album_payload = raw_track.get("albums") or []
    album = album_payload[0] if album_payload and isinstance(album_payload[0], dict) else {}
    duration_ms = raw_track.get("duration_ms")
    duration_seconds = int(duration_ms / 1000) if isinstance(duration_ms, int) else None
    available = raw_track.get("available")
    availability = "available" if available is True else ("unavailable" if available is False else None)

    return ProviderTrack(
        provider_id="yandex_music",
        external_id=track_id,
        album_external_id=str(album.get("id")) if album.get("id") is not None else None,
        title=str(raw_track.get("title", "")).strip(),
        artists=artists,
        album_title=str(album.get("title")).strip() if album.get("title") else None,
        duration_seconds=duration_seconds,
        explicit=bool(raw_track.get("content_warning")) if raw_track.get("content_warning") is not None else None,
        availability=availability,
        artwork_url=_artwork_url(raw_track, album),
        source_type="yandex_music",
        raw_payload_ref=f"track:{track_id}" if track_id else None,
        raw_data=raw_track,
    )


def map_yandex_album(raw_album: dict[str, Any], *, liked_at: Any = None) -> dict[str, Any]:
    """Return a stable provider-bound summary for a Yandex album."""
    album_id = str(raw_album.get("id") or "").strip()
    artists_payload = raw_album.get("artists") or []
    artists = [
        str(artist.get("name", "")).strip()
        for artist in artists_payload
        if isinstance(artist, dict) and artist.get("name")
    ]
    available = raw_album.get("available")
    availability = "available" if available is True else ("unavailable" if available is False else None)
    track_count = raw_album.get("track_count")
    if not isinstance(track_count, int):
        track_count = 0
    return {
        "providerId": "yandex_music",
        "externalId": album_id,
        "title": str(raw_album.get("title") or "").strip(),
        "artists": artists,
        "artworkUrl": _artwork_url({}, raw_album, size="400x400"),
        "trackCount": track_count,
        "year": raw_album.get("year"),
        "releaseDate": raw_album.get("release_date"),
        "availability": availability,
        "likedAt": str(liked_at) if liked_at is not None else None,
    }


def map_yandex_playlist(raw_playlist: dict) -> ProviderPlaylist:
    """Map normalized Yandex playlist payload into ProviderPlaylist."""
    playlist_id = str(raw_playlist.get("kind", ""))
    owner = raw_playlist.get("owner") if isinstance(raw_playlist.get("owner"), dict) else {}
    track_refs = raw_playlist.get("track_refs") or []
    if not track_refs and isinstance(raw_playlist.get("tracks"), list):
        track_refs = [
            str(item.get("id"))
            for item in raw_playlist["tracks"]
            if isinstance(item, dict) and item.get("id") is not None
        ]
    track_ids = tuple(str(track_id) for track_id in track_refs if track_id)

    return ProviderPlaylist(
        provider_id="yandex_music",
        external_id=playlist_id,
        title=str(raw_playlist.get("title", "")).strip(),
        owner_name=str(owner.get("name")).strip() if owner.get("name") else None,
        visibility=str(raw_playlist.get("visibility")).strip() if raw_playlist.get("visibility") else None,
        track_external_ids=track_ids,
        source_type="yandex_music",
        raw_payload_ref=f"playlist:{playlist_id}" if playlist_id else None,
        raw_data=raw_playlist,
    )


def map_track_source(track: ProviderTrack) -> TrackSource:
    """Create yandex_music track source from mapped ProviderTrack."""
    return TrackSource(
        track_id=f"provider:yandex_music:{track.external_id}",
        source_type="yandex_music",
        provider_id="yandex_music",
        external_id=track.external_id,
        availability=track.availability,
        raw_data={"raw_payload_ref": track.raw_payload_ref},
    )
