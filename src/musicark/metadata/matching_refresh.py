"""Targeted rematching after one explicit local metadata edit."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.matching.candidates import CandidateGenerator
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.indexer import LocalMatchIndex
from musicark.matching.input import MatchingInputRepository
from musicark.matching.models import MatchDecision, MatchMethod, MatchStatus, ScoredCandidate
from musicark.matching.policy import AMBIGUITY_MARGIN, AUTO_MATCH_THRESHOLD, CONFLICT_THRESHOLD
from musicark.matching.scoring import MatchScorer
from musicark.storage.matching_storage import MatchingStorageRepository


class TargetedMatchingRefresh:
    """Re-evaluate identities affected by one local file, then rebase unrelated fresh rows."""

    def __init__(self, database_path: Path, provider_id: str = "yandex_music") -> None:
        self._database_path = database_path
        self._provider_id = provider_id
        self._repo = MatchingStorageRepository(database_path)
        self._scorer = MatchScorer()
        self._index = LocalMatchIndex(database_path)
        self._input = MatchingInputRepository(database_path)

    def _local(self, local_file_id: int) -> dict[str, Any]:
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                """
                SELECT id, path, title, artists_json, album, duration_seconds, codec,
                       metadata_json, normalized_title, normalized_artists_text,
                       duration_bucket, modified_ns, updated_at
                FROM local_audio_files WHERE id=? AND availability='available'
                """,
                (int(local_file_id),),
            ).fetchone()
        if row is None:
            raise ValueError(f"Local file {local_file_id} was not found after re-index.")
        try:
            artists = json.loads(row[3] or "[]")
        except json.JSONDecodeError:
            artists = []
        try:
            metadata = json.loads(row[7] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": int(row[0]), "path": row[1], "title": row[2],
            "artists": artists if isinstance(artists, list) else [],
            "album": row[4], "duration_seconds": row[5], "codec": row[6],
            "metadata_json": metadata if isinstance(metadata, dict) else {},
            "tag_title_present": bool(isinstance(metadata, dict) and metadata.get("title")),
            "normalized_title": row[8] or "", "normalized_artists": row[9] or "",
            "duration_bucket": row[10], "modified_ns": row[11], "updated_at": row[12],
        }

    @staticmethod
    def _decide(
        provider: dict[str, Any], provider_fp: str, local_fp: str,
        candidates: list[ScoredCandidate],
    ) -> MatchDecision:
        provider_id = str(provider["provider_id"])
        external_id = str(provider["external_id"])
        payload = dict(provider["payload"])
        if not candidates:
            return MatchDecision(
                provider_id=provider_id,
                external_id=external_id,
                provider_payload=payload,
                provider_fingerprint=provider_fp,
                local_fingerprint=local_fp,
                status=MatchStatus.UNMATCHED,
                local_file_id=None,
                confidence=0.0,
                method=MatchMethod.AUTOMATIC,
                breakdown={},
                reason="no_candidates",
            )
        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        margin = best.confidence - second.confidence if second else 1.0
        if best.confidence >= AUTO_MATCH_THRESHOLD and margin >= AMBIGUITY_MARGIN:
            status, reason = MatchStatus.MATCHED, "auto_threshold_and_margin"
        elif best.confidence >= CONFLICT_THRESHOLD:
            status = MatchStatus.CONFLICT
            reason = "ambiguous_top_candidates" if second and margin < AMBIGUITY_MARGIN else "manual_review_threshold"
        else:
            status, reason = MatchStatus.UNMATCHED, "below_conflict_threshold"
        return MatchDecision(
            provider_id=provider_id,
            external_id=external_id,
            provider_payload=payload,
            provider_fingerprint=provider_fp,
            local_fingerprint=local_fp,
            status=status,
            local_file_id=best.local_file_id if status is not MatchStatus.UNMATCHED else None,
            confidence=best.confidence,
            method=best.method if status is not MatchStatus.UNMATCHED else MatchMethod.AUTOMATIC,
            breakdown=best.breakdown,
            reason=reason,
            candidates=tuple(candidates),
        )

    def _rebase(self, previous: str, current: str) -> int:
        if not previous or not current or previous == current:
            return 0
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE matching_results SET local_fingerprint=?
                    WHERE COALESCE(manual,0)=0 AND local_fingerprint=?
                    """,
                    (current, previous),
                )
                return max(0, int(cursor.rowcount))

    def run(self, local_file_id: int, *, previous_fingerprint: str) -> dict[str, Any]:
        self._input.sync_provider_tracks(self._provider_id)
        index_updates = self._index.refresh()
        current_fp = self._repo.local_library_fingerprint()
        local = self._local(local_file_id)
        providers = self._repo.list_provider_track_candidates(self._provider_id)
        candidates_to_recompute: list[dict[str, Any]] = []

        for provider in providers:
            external_id = str(provider["external_id"])
            existing = self._repo.get_existing_result(self._provider_id, external_id)
            if existing and existing.get("manual"):
                continue
            prelim = self._scorer.score(provider, local)
            references_edited = bool(existing and int(existing.get("local_file_id") or 0) == int(local_file_id))
            open_for_new = existing is None or str(existing.get("status") or "") in {"unmatched", "conflict"}
            if references_edited or (open_for_new and prelim.confidence >= CONFLICT_THRESHOLD):
                candidates_to_recompute.append(provider)

        generator = CandidateGenerator(self._repo, database_path=self._database_path)
        decisions: list[MatchDecision] = []
        for provider in candidates_to_recompute:
            provider_id = str(provider["provider_id"])
            external_id = str(provider["external_id"])
            rejected = self._repo.rejected_local_ids(provider_id, external_id)
            local_candidates = generator.generate(provider, excluded_local_ids=rejected)
            scored = sorted(
                (self._scorer.score(provider, candidate) for candidate in local_candidates),
                key=lambda item: item.confidence,
                reverse=True,
            )
            decisions.append(
                self._decide(
                    provider,
                    provider_fingerprint(provider_id, external_id, dict(provider["payload"])),
                    current_fp,
                    scored,
                )
            )
        self._repo.persist_batch(decisions)
        # Targeted decisions already carry current_fp, so this only advances unrelated
        # rows that were provably fresh before this one controlled file mutation.
        rebased = self._rebase(previous_fingerprint, current_fp)
        return {
            "localFileId": int(local_file_id),
            "recalculated": len(decisions),
            "rebasedUnrelated": rebased,
            "indexUpdates": index_updates,
            "comparisons": generator.comparison_count,
            "localFingerprint": current_fp,
        }
