"""Sequential cache-first external metadata resolver for one Local Library file."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.download.metadata import YandexTrackMetadata
from musicark.metadata.yandex import YandexMetadataGateway, identity_fields, metadata_fields

from .artwork import ExternalArtworkCache
from .cache import ExternalMetadataCache
from .credentials import ExternalCredentialStore
from .fingerprint import FingerprintError, FingerprintService
from .models import (
    Confidence,
    EvidenceType,
    ExternalArtworkCandidate,
    ExternalMetadataCandidate,
    MetadataEvidence,
)
from .network import ExternalNetworkTransport, NetworkSettingsStore
from .sources import (
    AcoustIdSource,
    CoverArtArchiveSource,
    DiscogsSource,
    ExternalSourceError,
    LastFmSource,
    MusicBrainzSource,
    SourceNotConfigured,
    SourceRateLimited,
    TheAudioDbSource,
)


class ExternalMetadataResolver:
    """Resolve candidates without mutating local audio or trusted Yandex identity state."""

    def __init__(self, database_path: Path, base_dir: Path | None = None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir
        self._credentials = ExternalCredentialStore()
        self._settings = NetworkSettingsStore(base_dir, self._credentials)
        self._transport = ExternalNetworkTransport(self._settings)
        self._cache = ExternalMetadataCache(database_path)
        self._fingerprints = FingerprintService(database_path)
        self._yandex = YandexMetadataGateway(base_dir, database_path)
        self._acoustid = AcoustIdSource(self._transport, self._credentials)
        self._musicbrainz = MusicBrainzSource(self._transport)
        self._caa = CoverArtArchiveSource(self._transport)
        self._artwork = ExternalArtworkCache(database_path, base_dir, self._transport)
        self._discogs = DiscogsSource(self._transport, self._credentials)
        self._audiodb = TheAudioDbSource(self._transport, self._credentials)
        self._lastfm = LastFmSource(self._transport, self._credentials)

    def _local(self, local_file_id: int) -> dict[str, Any]:
        with closing(sqlite3.connect(self._database_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, path, title, artists_json, album, year, duration_seconds,
                       source_provider_id, source_external_id, availability
                FROM local_audio_files WHERE id=?
                """,
                (int(local_file_id),),
            ).fetchone()
        if row is None or row["availability"] != "available":
            raise ValueError(f"Local file {local_file_id} is not available.")
        item = dict(row)
        try:
            item["artists"] = json.loads(item.get("artists_json") or "[]")
        except json.JSONDecodeError:
            item["artists"] = []
        return item

    @staticmethod
    def _file_key(local: dict[str, Any]) -> str:
        path = Path(str(local["path"]))
        stat = path.stat()
        modified = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        return f"{stat.st_size}:{modified}"

    @staticmethod
    def _candidate_id(local_file_id: int, item: ExternalMetadataCandidate) -> str:
        raw = "|".join((str(local_file_id), item.source, item.source_track_id or "", item.source_release_id or ""))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _remember_candidate(self, local_file_id: int, item: ExternalMetadataCandidate) -> dict[str, Any]:
        payload = item.as_dict()
        candidate_id = self._candidate_id(local_file_id, item)
        payload["candidateId"] = candidate_id
        self._cache.put(f"candidate:{local_file_id}:{candidate_id}", item.source, payload, ttl_seconds=86400)
        return payload

    def candidate(self, local_file_id: int, candidate_id: str) -> dict[str, Any]:
        cached = self._cache.get(f"candidate:{int(local_file_id)}:{candidate_id}")
        if cached is None or cached[0] is True or not isinstance(cached[1], dict):
            raise ValueError("External metadata candidate expired or was not found.")
        return dict(cached[1])

    def persist_candidate_identities(self, local_file_id: int, candidate_id: str) -> None:
        candidate = self.candidate(local_file_id, candidate_id)
        identities = candidate.get("identities") or {}
        if not isinstance(identities, dict):
            return
        source = str(candidate.get("source") or "external")
        confidence = str(candidate.get("confidence") or "possible")
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                for identity_type, identity_value in identities.items():
                    value = str(identity_value or "").strip()
                    key = str(identity_type or "").strip()
                    if not key or not value:
                        continue
                    conn.execute(
                        """
                        INSERT INTO local_external_identities(
                            local_file_id, identity_type, identity_value, source,
                            confidence, user_confirmed, updated_at
                        ) VALUES(?, ?, ?, ?, ?, 1, datetime('now'))
                        ON CONFLICT(local_file_id, identity_type, identity_value) DO UPDATE SET
                            source=excluded.source,
                            confidence=excluded.confidence,
                            user_confirmed=1,
                            updated_at=excluded.updated_at
                        """,
                        (int(local_file_id), key, value, source, confidence),
                    )

    @staticmethod
    def _yandex_candidate(metadata: YandexTrackMetadata, public: dict[str, Any]) -> ExternalMetadataCandidate:
        fields = metadata_fields(metadata)
        fields = {key: value for key, value in fields.items() if value not in (None, "", [])}
        identities = identity_fields(metadata)
        normalized = {str(key): str(value) for key, value in identities.items() if value not in (None, "", [])}
        artwork_payload = public.get("artwork") if isinstance(public, dict) else None
        artwork_path = str((artwork_payload or {}).get("cachePath") or "") if isinstance(artwork_payload, dict) else ""
        artwork = ExternalArtworkCandidate(source="yandex_music", cache_path=artwork_path) if artwork_path else None
        return ExternalMetadataCandidate(
            source="yandex_music",
            source_display_name="Yandex Music",
            source_track_id=metadata.external_id,
            source_release_id=metadata.album_id,
            fields=fields,
            identities=normalized,
            provenance={key: "yandex_music" for key in fields},
            confidence=Confidence.EXACT,
            artwork=artwork,
        )

    @staticmethod
    def _status(source: str, state: str, message: str = "") -> dict[str, str]:
        return {"source": source, "state": state, "message": message}

    def _call(self, statuses: list[dict[str, str]], source: str, fn):  # type: ignore[no-untyped-def]
        try:
            value = fn()
            statuses.append(self._status(source, "ok"))
            return value
        except SourceNotConfigured as exc:
            statuses.append(self._status(source, "not_configured", str(exc)))
        except SourceRateLimited as exc:
            statuses.append(self._status(source, "rate_limited", str(exc)))
        except ExternalSourceError as exc:
            statuses.append(self._status(source, "temporarily_unavailable", str(exc)))
        except Exception as exc:  # noqa: BLE001 - one provider must not abort the resolver.
            statuses.append(self._status(source, "unavailable", str(exc)))
        return None

    def _with_artwork(
        self,
        candidates: list[ExternalMetadataCandidate],
        statuses: list[dict[str, str]],
        *,
        limit: int = 3,
    ) -> list[ExternalMetadataCandidate]:
        result: list[ExternalMetadataCandidate] = []
        attempts = 0
        for item in candidates:
            if item.artwork is not None or not item.source_release_id or item.source != "musicbrainz" or attempts >= limit:
                result.append(item)
                continue
            attempts += 1
            try:
                url = self._caa.front_url(release_mbid=item.source_release_id, size=500)
                artwork = None
                if url:
                    artwork = self._artwork.fetch(
                        f"caa:release:{item.source_release_id}:500",
                        "cover_art_archive",
                        url,
                    )
                statuses.append(self._status("cover_art_archive", "ok" if artwork else "not_found"))
            except Exception as exc:  # noqa: BLE001 - artwork is optional.
                artwork = None
                statuses.append(self._status("cover_art_archive", "unavailable", str(exc)))
            result.append(ExternalMetadataCandidate(
                source=item.source,
                source_display_name=item.source_display_name,
                source_track_id=item.source_track_id,
                source_release_id=item.source_release_id,
                fields=item.fields,
                identities=item.identities,
                provenance=item.provenance,
                evidence=item.evidence,
                confidence=item.confidence,
                artwork=artwork,
            ))
        return result

    def identify(self, local_file_id: int, *, continue_search: bool = False) -> dict[str, Any]:
        local = self._local(local_file_id)
        resolution_key = f"resolve:{int(local_file_id)}:{self._file_key(local)}:{1 if continue_search else 0}"
        cached = self._cache.get(resolution_key)
        if cached is not None and cached[0] is False and isinstance(cached[1], dict):
            payload = dict(cached[1])
            payload["fromCache"] = True
            return payload

        statuses: list[dict[str, str]] = []
        candidates: list[ExternalMetadataCandidate] = []

        if local.get("source_provider_id") == "yandex_music" and local.get("source_external_id"):
            try:
                metadata = self._yandex.get(str(local["source_external_id"]))
                public = self._yandex.public_payload(metadata, cache_artwork=True)
                candidates.append(self._yandex_candidate(metadata, public))
                statuses.append(self._status("yandex_music", "ok"))
                if not continue_search:
                    return self._finish_resolution(resolution_key, local_file_id, candidates, statuses, early_stop=True)
            except Exception as exc:  # noqa: BLE001
                statuses.append(self._status("yandex_music", "unavailable", str(exc)))

        recording_mbid = ""
        acoustid_value = ""
        try:
            fp = self._fingerprints.fingerprint(int(local_file_id), Path(str(local["path"])))
            acoustid_results = self._call(statuses, "acoustid", lambda: self._acoustid.lookup(fp.fingerprint, fp.duration)) or []
            if acoustid_results:
                best = max(acoustid_results, key=lambda item: float(item.get("score") or 0))
                acoustid_value = str(best.get("acoustid") or "")
                mbids = best.get("recordingMbids") or []
                if mbids:
                    recording_mbid = str(mbids[0])
        except FingerprintError as exc:
            statuses.append(self._status("acoustid", "fingerprint_unavailable", str(exc)))

        if recording_mbid:
            items = self._call(statuses, "musicbrainz", lambda: self._musicbrainz.recording(recording_mbid)) or []
            if acoustid_value:
                enriched: list[ExternalMetadataCandidate] = []
                for item in items:
                    identities = dict(item.identities)
                    identities["acoustid"] = acoustid_value
                    evidence = (*item.evidence, MetadataEvidence(EvidenceType.ACOUSTID_FINGERPRINT, "acoustid", acoustid_value))
                    enriched.append(ExternalMetadataCandidate(
                        source=item.source, source_display_name=item.source_display_name,
                        source_track_id=item.source_track_id, source_release_id=item.source_release_id,
                        fields=item.fields, identities=identities, provenance=item.provenance,
                        evidence=evidence, confidence=item.confidence, artwork=item.artwork,
                    ))
                items = enriched
            items = self._with_artwork(items, statuses)
            candidates.extend(items)
            if any(item.confidence in {Confidence.EXACT, Confidence.STRONG} and item.source_release_id for item in items) and not continue_search:
                return self._finish_resolution(resolution_key, local_file_id, candidates, statuses, early_stop=True)

        title = str(local.get("title") or Path(str(local["path"])).stem).strip()
        artists = [str(item).strip() for item in local.get("artists") or [] if str(item).strip()]
        artist = artists[0] if artists else ""
        album = str(local.get("album") or "").strip()
        if title:
            mb_items = self._call(statuses, "musicbrainz", lambda: self._musicbrainz.search(title=title, artist=artist, album=album)) or []
            mb_items = self._with_artwork(mb_items, statuses)
            candidates.extend(mb_items)
            if any(item.confidence in {Confidence.EXACT, Confidence.STRONG} for item in mb_items) and not continue_search:
                return self._finish_resolution(resolution_key, local_file_id, candidates, statuses, early_stop=True)

        if continue_search or not candidates:
            candidates.extend(self._call(statuses, "discogs", lambda: self._discogs.search(title=title, artist=artist, album=album)) or [])
            candidates.extend(self._call(statuses, "theaudiodb", lambda: self._audiodb.search(title=title, artist=artist)) or [])
            candidates.extend(self._call(statuses, "lastfm", lambda: self._lastfm.search(title=title, artist=artist, recording_mbid=recording_mbid)) or [])

        return self._finish_resolution(resolution_key, local_file_id, candidates, statuses, early_stop=False)

    def search(self, local_file_id: int, *, title: str, artist: str = "", album: str = "", continue_search: bool = False) -> dict[str, Any]:
        normalized = "|".join((title.strip().casefold(), artist.strip().casefold(), album.strip().casefold(), "1" if continue_search else "0"))
        cache_key = f"search:{int(local_file_id)}:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"
        cached = self._cache.get(cache_key)
        if cached is not None and cached[0] is False and isinstance(cached[1], dict):
            payload = dict(cached[1])
            payload["fromCache"] = True
            return payload
        statuses: list[dict[str, str]] = []
        candidates = self._call(statuses, "musicbrainz", lambda: self._musicbrainz.search(title=title, artist=artist, album=album)) or []
        candidates = self._with_artwork(candidates, statuses)
        if continue_search or not candidates:
            candidates.extend(self._call(statuses, "discogs", lambda: self._discogs.search(title=title, artist=artist, album=album)) or [])
            candidates.extend(self._call(statuses, "theaudiodb", lambda: self._audiodb.search(title=title, artist=artist)) or [])
            candidates.extend(self._call(statuses, "lastfm", lambda: self._lastfm.search(title=title, artist=artist)) or [])
        payload = self._response(local_file_id, candidates, statuses, early_stop=False)
        self._cache.put(cache_key, "resolver", payload, ttl_seconds=3600)
        return payload

    def _finish_resolution(
        self,
        cache_key: str,
        local_file_id: int,
        candidates: list[ExternalMetadataCandidate],
        statuses: list[dict[str, str]],
        *,
        early_stop: bool,
    ) -> dict[str, Any]:
        payload = self._response(local_file_id, candidates, statuses, early_stop=early_stop)
        self._cache.put(cache_key, "resolver", payload, negative=not bool(payload["items"]), ttl_seconds=3600 if payload["items"] else 300)
        return payload

    def _response(self, local_file_id: int, candidates: list[ExternalMetadataCandidate], statuses: list[dict[str, str]], *, early_stop: bool) -> dict[str, Any]:
        unique: list[ExternalMetadataCandidate] = []
        seen: set[tuple[str, str | None, str | None]] = set()
        for item in candidates:
            key = (item.source, item.source_track_id, item.source_release_id)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        order = {Confidence.EXACT: 0, Confidence.STRONG: 1, Confidence.POSSIBLE: 2, Confidence.WEAK: 3, Confidence.AMBIGUOUS: 4}
        unique.sort(key=lambda item: order[item.confidence])
        return {
            "localFileId": int(local_file_id),
            "count": len(unique),
            "items": [self._remember_candidate(local_file_id, item) for item in unique[:30]],
            "sources": statuses,
            "earlyStop": early_stop,
            "fromCache": False,
        }
