"""Rich AcoustID lookup that returns MusicBrainz-backed metadata without calling musicbrainz.org."""

from __future__ import annotations

import threading
import time
from typing import Any

from .credentials import ExternalCredentialStore
from .models import Confidence, EvidenceType, ExternalMetadataCandidate, MetadataEvidence
from .network import ExternalNetworkTransport
from .sources import ExternalSourceError, SourceNotConfigured, SourceRateLimited


class AcoustIdMetadataSource:
    """Resolve a Chromaprint fingerprint to MusicBrainz-backed candidates via AcoustID.

    AcoustID's public lookup supports rich `meta` values including recordings,
    releases, release groups and ISRCs. Using those fields avoids making
    musicbrainz.org a mandatory runtime hop after a successful fingerprint match.
    """

    source_id = "acoustid"
    display_name = "AcoustID"

    def __init__(self, transport: ExternalNetworkTransport, credentials: ExternalCredentialStore) -> None:
        self._transport = transport
        self._credentials = credentials
        self._last_request = 0.0
        self._rate_lock = threading.Lock()

    def _wait(self) -> None:
        # AcoustID asks clients to stay at or below 3 requests/second.
        with self._rate_lock:
            delay = (1.0 / 3.0) - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()

    @staticmethod
    def _confidence(score: float) -> Confidence:
        if score >= 0.95:
            return Confidence.STRONG
        if score >= 0.80:
            return Confidence.POSSIBLE
        return Confidence.WEAK

    @staticmethod
    def _artist_names(recording: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for raw in recording.get("artists") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _isrcs(recording: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for raw in recording.get("isrcs") or []:
            if isinstance(raw, str) and raw.strip():
                values.append(raw.strip())
            elif isinstance(raw, dict):
                value = str(raw.get("id") or raw.get("isrc") or "").strip()
                if value:
                    values.append(value)
        return values

    @staticmethod
    def _releases(recording: dict[str, Any]) -> list[dict[str, Any]]:
        releases: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(raw: Any, *, fallback_group: dict[str, Any] | None = None) -> None:
            if not isinstance(raw, dict):
                return
            release_id = str(raw.get("id") or "").strip()
            if not release_id or release_id in seen:
                return
            item = dict(raw)
            if fallback_group is not None:
                item.setdefault("releasegroup", fallback_group)
            seen.add(release_id)
            releases.append(item)

        for raw in recording.get("releases") or []:
            add(raw)
        for group in recording.get("releasegroups") or []:
            if not isinstance(group, dict):
                continue
            for raw in group.get("releases") or []:
                add(raw, fallback_group=group)
        return releases

    @staticmethod
    def _release_groups(recording: dict[str, Any]) -> list[dict[str, Any]]:
        return [raw for raw in (recording.get("releasegroups") or []) if isinstance(raw, dict)]

    def lookup(self, fingerprint: str, duration: int) -> list[ExternalMetadataCandidate]:
        key = self._credentials.get("acoustid_key")
        if not key:
            raise SourceNotConfigured("AcoustID application key is not configured.")
        self._wait()
        response = self._transport.get(
            "https://api.acoustid.org/v2/lookup",
            params={
                "client": key,
                "duration": int(duration),
                "fingerprint": fingerprint,
                "meta": "recordings releases releasegroups isrcs compress",
                "format": "json",
            },
            headers={"User-Agent": "MusicArk/0.12.0"},
        )
        if response.status_code == 429:
            raise SourceRateLimited("AcoustID rate limit reached.")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise ExternalSourceError("AcoustID lookup failed.")

        candidates: list[ExternalMetadataCandidate] = []
        for raw_result in payload.get("results") or []:
            if not isinstance(raw_result, dict):
                continue
            acoustid = str(raw_result.get("id") or "").strip()
            try:
                score = float(raw_result.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            for recording in raw_result.get("recordings") or []:
                if not isinstance(recording, dict):
                    continue
                recording_mbid = str(recording.get("id") or "").strip()
                if not recording_mbid:
                    continue
                title = str(recording.get("title") or "").strip()
                artists = self._artist_names(recording)
                isrcs = self._isrcs(recording)
                try:
                    recording_duration = int(round(float(recording.get("duration")))) if recording.get("duration") is not None else None
                except (TypeError, ValueError):
                    recording_duration = None

                releases = self._releases(recording)
                groups = self._release_groups(recording)
                variants: list[tuple[dict[str, Any] | None, dict[str, Any] | None]] = []
                if releases:
                    for release in releases:
                        group = release.get("releasegroup") if isinstance(release.get("releasegroup"), dict) else None
                        variants.append((release, group))
                elif groups:
                    variants.extend((None, group) for group in groups)
                else:
                    variants.append((None, None))

                for release, group in variants:
                    release_id = str((release or {}).get("id") or "").strip()
                    group_id = str((group or {}).get("id") or "").strip()
                    album = str((release or {}).get("title") or (group or {}).get("title") or "").strip()
                    fields: dict[str, Any] = {
                        "title": title or None,
                        "artists": artists,
                        "album": album or None,
                        "durationSeconds": recording_duration,
                        "isrc": isrcs[0] if isrcs else None,
                    }
                    fields = {name: value for name, value in fields.items() if value not in (None, "", [])}
                    identities: dict[str, str] = {
                        "musicbrainz_recording_mbid": recording_mbid,
                    }
                    if acoustid:
                        identities["acoustid"] = acoustid
                    if release_id:
                        identities["musicbrainz_release_mbid"] = release_id
                    if group_id:
                        identities["musicbrainz_release_group_mbid"] = group_id
                    if isrcs:
                        identities["isrc"] = isrcs[0]
                    evidence = (
                        MetadataEvidence(EvidenceType.ACOUSTID_FINGERPRINT, self.source_id, acoustid or recording_mbid),
                        MetadataEvidence(EvidenceType.EXACT_RECORDING_MBID, self.source_id, recording_mbid),
                    )
                    candidates.append(ExternalMetadataCandidate(
                        source=self.source_id,
                        source_display_name=self.display_name,
                        source_track_id=recording_mbid,
                        source_release_id=release_id or None,
                        fields=fields,
                        identities=identities,
                        provenance={name: self.source_id for name in fields},
                        evidence=evidence,
                        confidence=self._confidence(score),
                    ))
        return candidates
