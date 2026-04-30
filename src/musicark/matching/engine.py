"""Matching-engine that links provider tracks with local audio files."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.matching_storage import MatchingStorageRepository

from .models import MatchConflict, MatchMethod, Track, TrackLink
from .normalize import normalize_text


class MatchingEngine:
    """Computes canonical links from provider/local data with confidence scoring."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._storage = MatchingStorageRepository(database_path)
        self._audit = AuditLogRepository(database_path)

    def run(self) -> dict[str, int]:
        provider_tracks = self._storage.list_provider_track_candidates()
        local_files = self._storage.list_local_audio_files()

        linked = 0
        conflicts = 0
        skipped = 0

        for candidate in provider_tracks:
            match = self._best_local_match(candidate, local_files)
            if match is None:
                skipped += 1
                continue
            confidence = match["confidence"]
            local = match["local"]

            canonical_track = self._to_canonical_track(candidate)
            canonical_track_id = self._storage.upsert_track(canonical_track)

            if confidence >= 0.85:
                self._storage.upsert_track_link(
                    TrackLink(
                        track_id=canonical_track_id,
                        source_provider_id=candidate["provider_id"],
                        source_external_id=candidate["external_id"],
                        local_file_id=local["id"],
                        confidence=confidence,
                        match_method=match["method"],
                        metadata_json={"candidate": candidate["external_id"]},
                    )
                )
                linked += 1
            elif confidence >= 0.60:
                self._storage.insert_conflict(
                    MatchConflict(
                        source_provider_id=candidate["provider_id"],
                        source_external_id=candidate["external_id"],
                        local_file_id=local["id"],
                        confidence=confidence,
                        reason="confidence_between_0.60_and_0.85",
                    )
                )
                conflicts += 1
            else:
                skipped += 1

        self._audit.append(
            AuditEvent(
                event_type="matching_run",
                entity_type="matching_engine",
                entity_id="canonical_library",
                status="success",
                details=f"linked={linked} conflicts={conflicts} skipped={skipped}",
            )
        )
        return {"linked": linked, "conflicts": conflicts, "skipped": skipped}

    def list_conflicts(self) -> list[dict]:
        return self._storage.list_open_conflicts()

    def accept(self, conflict_id: int) -> None:
        # Resolve canonical track using same source candidate.
        conflicts = self._storage.list_open_conflicts()
        row = next((item for item in conflicts if item["id"] == conflict_id), None)
        if row is None:
            raise ValueError(f"Conflict {conflict_id} not found.")
        # Create/reuse canonical track from source payload.
        source = next(
            (
                item
                for item in self._storage.list_provider_track_candidates()
                if item["provider_id"] == row["source_provider_id"]
                and item["external_id"] == row["source_external_id"]
            ),
            None,
        )
        if source is None:
            raise ValueError("Provider track candidate for conflict is missing.")
        track_id = self._storage.upsert_track(self._to_canonical_track(source))
        self._storage.accept_conflict(conflict_id, track_id)
        self._audit.append(
            AuditEvent(
                event_type="matching_conflict_accepted",
                entity_type="matching_conflict",
                entity_id=str(conflict_id),
                status="success",
                details=f"track_id={track_id}",
            )
        )

    def _to_canonical_track(self, candidate: dict[str, Any]) -> Track:
        payload = candidate["payload"]
        artists = tuple(payload.get("artists") or ())
        normalized_title = normalize_text(payload.get("title"))
        normalized_artists = tuple(normalize_text(artist) for artist in artists if artist)
        return Track(
            title=str(payload.get("title", "")),
            artists=artists,
            album=payload.get("album_title"),
            duration_seconds=(
                float(payload.get("duration_seconds"))
                if payload.get("duration_seconds") is not None
                else None
            ),
            normalized_title=normalized_title,
            normalized_artists=normalized_artists,
        )

    def _best_local_match(self, candidate: dict[str, Any], local_files: list[dict]) -> dict | None:
        payload = candidate["payload"]
        source_id = str(candidate["external_id"])
        best: dict | None = None
        for local in local_files:
            score, method = self._score_candidate(payload, source_id, local)
            if best is None or score > best["confidence"]:
                best = {"confidence": score, "method": method, "local": local}
        return best

    def _score_candidate(self, payload: dict, source_id: str, local: dict) -> tuple[float, MatchMethod]:
        path = str(local["path"]).lower()
        title = normalize_text(payload.get("title"))
        artists = [normalize_text(a) for a in (payload.get("artists") or [])]
        duration = payload.get("duration_seconds")

        # Strong exact-id heuristic for yandex_{id}.mp3 downloads.
        if source_id and source_id.lower() in path:
            return 0.99, MatchMethod.EXACT_ID

        file_name_norm = normalize_text(Path(path).stem)
        score = 0.0
        if title and title in file_name_norm:
            score += 0.55
        artist_hit = 0
        for artist in artists:
            if artist and artist in file_name_norm:
                artist_hit += 1
        if artist_hit:
            score += min(0.30, artist_hit * 0.15)

        local_duration = local.get("duration_seconds")
        if duration is not None and local_duration is not None:
            delta = abs(float(duration) - float(local_duration))
            if delta <= 2:
                score += 0.15
            elif delta <= 5:
                score += 0.08

        method = MatchMethod.TITLE_ARTIST_DURATION if score >= 0.70 else MatchMethod.TITLE_ARTIST
        return min(score, 0.95), method
