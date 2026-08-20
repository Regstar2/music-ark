"""Read-only external metadata source adapters used by the v0.12 resolver."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

from .credentials import ExternalCredentialStore
from .models import Confidence, EvidenceType, ExternalMetadataCandidate, MetadataEvidence
from .network import ExternalNetworkTransport


class ExternalSourceError(RuntimeError):
    pass


class SourceNotConfigured(ExternalSourceError):
    pass


class SourceRateLimited(ExternalSourceError):
    pass


class RateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self._interval = max(0.0, interval_seconds)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            delay = self._interval - (time.monotonic() - self._last)
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


def _json(response: Any) -> dict[str, Any]:
    if response.status_code == 429:
        raise SourceRateLimited("External metadata source rate limit reached.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ExternalSourceError("External metadata source returned invalid JSON.")
    return payload


class AcoustIdSource:
    source_id = "acoustid"

    def __init__(self, transport: ExternalNetworkTransport, credentials: ExternalCredentialStore) -> None:
        self._transport = transport
        self._credentials = credentials
        self._rate = RateLimiter(1 / 3)

    def lookup(self, fingerprint: str, duration: int) -> list[dict[str, Any]]:
        key = self._credentials.get("acoustid_key")
        if not key:
            raise SourceNotConfigured("AcoustID application key is not configured.")
        self._rate.wait()
        payload = _json(self._transport.get(
            "https://api.acoustid.org/v2/lookup",
            params={"client": key, "duration": int(duration), "fingerprint": fingerprint, "meta": "recordingids", "format": "json"},
        ))
        if payload.get("status") != "ok":
            raise ExternalSourceError("AcoustID lookup failed.")
        results: list[dict[str, Any]] = []
        for raw in payload.get("results") or []:
            if not isinstance(raw, dict):
                continue
            recordings = [str(x.get("id")) for x in (raw.get("recordings") or []) if isinstance(x, dict) and x.get("id")]
            results.append({"acoustid": str(raw.get("id") or ""), "score": float(raw.get("score") or 0), "recordingMbids": recordings})
        return results


class MusicBrainzSource:
    source_id = "musicbrainz"
    display_name = "MusicBrainz"

    def __init__(self, transport: ExternalNetworkTransport, *, user_agent: str = "MusicArk/0.12.0 (https://github.com/Regstar2/music-ark)") -> None:
        self._transport = transport
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._rate = RateLimiter(1.0)

    def _get(self, entity: str, value: str | None = None, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._rate.wait()
        url = f"https://musicbrainz.org/ws/2/{entity}" + (f"/{value}" if value else "")
        query = {"fmt": "json", **(params or {})}
        return _json(self._transport.get(url, params=query, headers=self._headers))

    @staticmethod
    def _artist_names(credit: Any) -> list[str]:
        values: list[str] = []
        for item in credit or []:
            if not isinstance(item, dict):
                continue
            artist = item.get("artist") if isinstance(item.get("artist"), dict) else {}
            name = str(item.get("name") or artist.get("name") or "").strip()
            if name:
                values.append(name)
        return values

    def recording(self, mbid: str) -> list[ExternalMetadataCandidate]:
        raw = self._get("recording", mbid, params={"inc": "artists+releases+isrcs"})
        return self._recording_candidates(raw, exact=True)

    def search(self, *, title: str, artist: str = "", album: str = "", isrc: str = "") -> list[ExternalMetadataCandidate]:
        if isrc:
            query = f'isrc:"{isrc}"'
        else:
            terms = [f'recording:"{title}"']
            if artist:
                terms.append(f'artist:"{artist}"')
            if album:
                terms.append(f'release:"{album}"')
            query = " AND ".join(terms)
        payload = self._get("recording", params={"query": query, "limit": 12})
        candidates: list[ExternalMetadataCandidate] = []
        for raw in payload.get("recordings") or []:
            if isinstance(raw, dict):
                candidates.extend(self._recording_candidates(raw, exact=bool(isrc)))
        return candidates

    def _recording_candidates(self, raw: dict[str, Any], *, exact: bool) -> list[ExternalMetadataCandidate]:
        recording_id = str(raw.get("id") or "")
        releases = [item for item in (raw.get("releases") or []) if isinstance(item, dict)] or [None]
        artists = self._artist_names(raw.get("artist-credit"))
        isrcs = [str(item) for item in (raw.get("isrcs") or []) if item]
        result: list[ExternalMetadataCandidate] = []
        for release in releases:
            release_id = str((release or {}).get("id") or "") or None
            date = str((release or {}).get("date") or "") or None
            year = int(date[:4]) if date and len(date) >= 4 and date[:4].isdigit() else None
            fields: dict[str, Any] = {
                "title": raw.get("title"),
                "artists": artists,
                "album": (release or {}).get("title"),
                "releaseDate": date,
                "year": year,
                "isrc": isrcs[0] if isrcs else None,
                "durationSeconds": (float(raw.get("length")) / 1000.0) if raw.get("length") is not None else None,
            }
            fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
            identities = {"musicbrainz_recording_mbid": recording_id}
            if release_id:
                identities["musicbrainz_release_mbid"] = release_id
            if isrcs:
                identities["isrc"] = isrcs[0]
            evidence = [MetadataEvidence(EvidenceType.EXACT_RECORDING_MBID, self.source_id, recording_id)] if exact else []
            if isrcs and exact:
                evidence.append(MetadataEvidence(EvidenceType.EXACT_ISRC, self.source_id, isrcs[0]))
            result.append(ExternalMetadataCandidate(
                source=self.source_id,
                source_display_name=self.display_name,
                source_track_id=recording_id,
                source_release_id=release_id,
                fields=fields,
                identities=identities,
                provenance={key: self.source_id for key in fields},
                evidence=tuple(evidence),
                confidence=Confidence.EXACT if exact and release_id else (Confidence.STRONG if exact else Confidence.POSSIBLE),
            ))
        return result


class CoverArtArchiveSource:
    source_id = "cover_art_archive"

    def __init__(self, transport: ExternalNetworkTransport) -> None:
        self._transport = transport

    def front_url(self, *, release_mbid: str | None, release_group_mbid: str | None = None, size: int = 500) -> str | None:
        if size not in {250, 500, 1200}:
            raise ValueError("Cover Art Archive thumbnail size must be 250, 500 or 1200.")
        paths = []
        if release_mbid:
            paths.append(f"release/{release_mbid}/front-{size}")
        if release_group_mbid:
            paths.append(f"release-group/{release_group_mbid}/front-{size}")
        for path in paths:
            response = self._transport.get(f"https://coverartarchive.org/{path}", headers={"Accept": "image/*"})
            if response.status_code == 404:
                continue
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if location:
                    return location
            if response.status_code == 200:
                return str(response.url)
        return None


class DiscogsSource:
    """Optional release fallback. The API is disabled until a user token is configured."""

    source_id = "discogs"

    def __init__(self, transport: ExternalNetworkTransport, credentials: ExternalCredentialStore) -> None:
        self._transport = transport
        self._credentials = credentials
        self._rate = RateLimiter(1.0)

    def search(self, *, title: str, artist: str = "", album: str = "") -> list[ExternalMetadataCandidate]:
        token = self._credentials.get("discogs_token")
        if not token:
            raise SourceNotConfigured("Discogs token is not configured.")
        self._rate.wait()
        params: dict[str, Any] = {"type": "release", "track": title, "per_page": 10}
        if artist:
            params["artist"] = artist
        if album:
            params["release_title"] = album
        payload = _json(self._transport.get(
            "https://api.discogs.com/database/search",
            params=params,
            headers={"Authorization": f"Discogs token={token}", "User-Agent": "MusicArk/0.12.0"},
        ))
        result: list[ExternalMetadataCandidate] = []
        for raw in payload.get("results") or []:
            if not isinstance(raw, dict):
                continue
            release_id = str(raw.get("id") or "")
            fields = {"album": raw.get("title"), "year": raw.get("year"), "genres": raw.get("genre") or []}
            fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
            result.append(ExternalMetadataCandidate(
                source=self.source_id, source_display_name="Discogs", source_release_id=release_id or None,
                fields=fields, identities={"discogs_release_id": release_id} if release_id else {},
                provenance={key: self.source_id for key in fields}, confidence=Confidence.WEAK,
            ))
        return result


class TheAudioDbSource:
    source_id = "theaudiodb"

    def __init__(self, transport: ExternalNetworkTransport, credentials: ExternalCredentialStore) -> None:
        self._transport = transport
        self._credentials = credentials
        self._rate = RateLimiter(2.0)

    def search(self, *, title: str, artist: str = "") -> list[ExternalMetadataCandidate]:
        key = self._credentials.get("theaudiodb_key")
        if not key:
            raise SourceNotConfigured("TheAudioDB API key is not configured.")
        self._rate.wait()
        payload = _json(self._transport.get(
            f"https://www.theaudiodb.com/api/v1/json/{key}/searchtrack.php",
            params={"s": artist, "t": title},
        ))
        result: list[ExternalMetadataCandidate] = []
        for raw in payload.get("track") or []:
            if not isinstance(raw, dict):
                continue
            track_id = str(raw.get("idTrack") or "")
            album_id = str(raw.get("idAlbum") or "")
            fields = {
                "title": raw.get("strTrack"), "artists": [raw.get("strArtist")] if raw.get("strArtist") else [],
                "album": raw.get("strAlbum"), "genres": [raw.get("strGenre")] if raw.get("strGenre") else [],
                "durationSeconds": (float(raw.get("intDuration")) / 1000.0) if str(raw.get("intDuration") or "").isdigit() else None,
            }
            fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
            identities = {}
            if track_id: identities["theaudiodb_track_id"] = track_id
            if album_id: identities["theaudiodb_album_id"] = album_id
            result.append(ExternalMetadataCandidate(
                source=self.source_id, source_display_name="TheAudioDB", source_track_id=track_id or None,
                source_release_id=album_id or None, fields=fields, identities=identities,
                provenance={key: self.source_id for key in fields}, confidence=Confidence.WEAK,
            ))
        return result


class LastFmSource:
    source_id = "lastfm"

    def __init__(self, transport: ExternalNetworkTransport, credentials: ExternalCredentialStore) -> None:
        self._transport = transport
        self._credentials = credentials
        self._rate = RateLimiter(1.0)

    def search(self, *, title: str, artist: str = "", recording_mbid: str = "") -> list[ExternalMetadataCandidate]:
        key = self._credentials.get("lastfm_key")
        if not key:
            raise SourceNotConfigured("Last.fm API key is not configured.")
        if not recording_mbid and (not title or not artist):
            return []
        self._rate.wait()
        params: dict[str, Any] = {"method": "track.getInfo", "api_key": key, "format": "json", "autocorrect": 1}
        if recording_mbid:
            params["mbid"] = recording_mbid
        else:
            params.update({"track": title, "artist": artist})
        payload = _json(self._transport.get("https://ws.audioscrobbler.com/2.0/", params=params))
        raw = payload.get("track")
        if not isinstance(raw, dict):
            return []
        artist_obj = raw.get("artist") if isinstance(raw.get("artist"), dict) else {}
        album_obj = raw.get("album") if isinstance(raw.get("album"), dict) else {}
        fields = {
            "title": raw.get("name"), "artists": [artist_obj.get("name")] if artist_obj.get("name") else [],
            "album": album_obj.get("title"),
            "durationSeconds": (float(raw.get("duration")) / 1000.0) if str(raw.get("duration") or "").isdigit() else None,
            "genres": [str(x.get("name")) for x in ((raw.get("toptags") or {}).get("tag") or []) if isinstance(x, dict) and x.get("name")],
        }
        fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
        mbid = str(raw.get("mbid") or recording_mbid or "")
        identities = {"musicbrainz_recording_mbid": mbid} if mbid else {}
        return [ExternalMetadataCandidate(
            source=self.source_id, source_display_name="Last.fm", source_track_id=mbid or None,
            fields=fields, identities=identities, provenance={key: self.source_id for key in fields},
            confidence=Confidence.POSSIBLE if recording_mbid else Confidence.WEAK,
        )]
