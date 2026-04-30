"""Mapping utilities from Yandex payloads to universal provider models."""

from __future__ import annotations

from .models import ProviderPlaylist, ProviderTrack, TrackSource


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
        source_type="yandex_music",
        raw_payload_ref=f"track:{track_id}" if track_id else None,
        raw_data=raw_track,
    )


def map_yandex_playlist(raw_playlist: dict) -> ProviderPlaylist:
    """Map normalized Yandex playlist payload into ProviderPlaylist."""
    playlist_id = str(raw_playlist.get("kind", ""))
    owner = raw_playlist.get("owner") if isinstance(raw_playlist.get("owner"), dict) else {}
    track_refs = raw_playlist.get("track_refs") or []
    if not track_refs and isinstance(raw_playlist.get("tracks"), list):
        # Scanner may pass raw playlist track records.
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
