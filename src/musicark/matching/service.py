"""Application-level orchestration for MusicArk v0.5 matching."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

from musicark.core.config import load_config
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository
from .candidates import CandidateGenerator
from .indexer import LocalMatchIndex
from .input import MatchingInputRepository
from .models import MatchDecision, MatchMethod, MatchStatus, ScoredCandidate
from .policy import AMBIGUITY_MARGIN, AUTO_MATCH_THRESHOLD, CONFLICT_THRESHOLD, MATCHER_VERSION
from .result_queries import MatchingResultQueries
from .scoring import MatchScorer


class MatchingService:
    """Offline-only matching orchestration over cached provider and local data."""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        database_path: Path | None = None,
        provider_id: str = "yandex_music",
    ) -> None:
        self._base_dir = base_dir
        self._provider_id = provider_id
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._repository = MatchingStorageRepository(self._database_path)
        self._queries = MatchingResultQueries(self._database_path)
        self._audit = AuditLogRepository(self._database_path)
        self._scorer = MatchScorer()
        self._local_index = LocalMatchIndex(self._database_path)
        self._input = MatchingInputRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    @staticmethod
    def _provider_fingerprint(provider: dict[str, Any]) -> str:
        payload = provider["payload"]
        relevant = {
            "provider_id": provider["provider_id"],
            "external_id": provider["external_id"],
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

    def summary(self) -> dict[str, Any]:
        self._input.sync_provider_tracks(self._provider_id)
        return self._repository.summary(self._provider_id)

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        provider_identity_count = self._input.sync_provider_tracks(self._provider_id)
        stale = self._repository.cleanup_stale_links()
        index_updates = self._local_index.refresh()
        local_fingerprint = self._repository.local_library_fingerprint()
        providers = self._repository.list_provider_track_candidates(self._provider_id)
        generator = CandidateGenerator(
            self._repository,
            database_path=self._database_path,
        )
        batch: list[MatchDecision] = []
        unchanged = 0

        for provider in providers:
            provider_id = str(provider["provider_id"])
            external_id = str(provider["external_id"])
            provider_fingerprint = self._provider_fingerprint(provider)
            existing = self._repository.get_existing_result(provider_id, external_id)
            if existing and existing.get("manual"):
                unchanged += 1
                continue
            if (
                existing
                and int(existing.get("matcher_version") or 0) == MATCHER_VERSION
                and existing.get("provider_fingerprint") == provider_fingerprint
                and existing.get("local_fingerprint") == local_fingerprint
            ):
                unchanged += 1
                continue

            rejected = self._repository.rejected_local_ids(provider_id, external_id)
            local_candidates = generator.generate(provider, excluded_local_ids=rejected)
            scored = sorted(
                (self._scorer.score(provider, local) for local in local_candidates),
                key=lambda item: item.confidence,
                reverse=True,
            )
            batch.append(
                self._decide(
                    provider,
                    provider_fingerprint=provider_fingerprint,
                    local_fingerprint=local_fingerprint,
                    candidates=scored,
                )
            )
            if len(batch) >= 250:
                self._repository.persist_batch(batch)
                batch.clear()
        self._repository.persist_batch(batch)

        summary = self._repository.summary(self._provider_id)
        duration = max(0.0, time.perf_counter() - started)
        result = {
            "total": summary["processed"],
            "providerIdentities": provider_identity_count,
            "matched": summary["matched"],
            "conflicts": summary["conflicts"],
            "unmatched": summary["unmatched"],
            "unchanged": unchanged,
            "invalidated": stale,
            "indexUpdates": index_updates,
            "comparisons": generator.comparison_count,
            "durationSeconds": round(duration, 4),
            "matcherVersion": MATCHER_VERSION,
            "summary": summary,
        }
        self._audit.append(
            AuditEvent(
                event_type="matching_run",
                entity_type="matching_service",
                entity_id=self._provider_id,
                status="success",
                details=(
                    f"matched={result['matched']} conflicts={result['conflicts']} "
                    f"unmatched={result['unmatched']} unchanged={unchanged} "
                    f"comparisons={generator.comparison_count}"
                ),
            )
        )
        return result

    @staticmethod
    def _decide(
        provider: dict[str, Any],
        *,
        provider_fingerprint: str,
        local_fingerprint: str,
        candidates: list[ScoredCandidate],
    ) -> MatchDecision:
        provider_id = str(provider["provider_id"])
        external_id = str(provider["external_id"])
        payload = dict(provider["payload"])
        if not candidates:
            return MatchDecision(
                provider_id,
                external_id,
                payload,
                provider_fingerprint,
                local_fingerprint,
                MatchStatus.UNMATCHED,
                None,
                0.0,
                MatchMethod.AUTOMATIC,
                {},
                "no_candidates",
            )

        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        margin = best.confidence - second.confidence if second else 1.0
        if best.confidence >= AUTO_MATCH_THRESHOLD and margin >= AMBIGUITY_MARGIN:
            status = MatchStatus.MATCHED
            reason = "auto_threshold_and_margin"
        elif best.confidence >= CONFLICT_THRESHOLD:
            status = MatchStatus.CONFLICT
            reason = (
                "ambiguous_top_candidates"
                if second and margin < AMBIGUITY_MARGIN
                else "manual_review_threshold"
            )
        else:
            status = MatchStatus.UNMATCHED
            reason = "below_conflict_threshold"

        return MatchDecision(
            provider_id=provider_id,
            external_id=external_id,
            provider_payload=payload,
            provider_fingerprint=provider_fingerprint,
            local_fingerprint=local_fingerprint,
            status=status,
            local_file_id=(
                best.local_file_id if status is not MatchStatus.UNMATCHED else None
            ),
            confidence=best.confidence,
            method=(
                best.method if status is not MatchStatus.UNMATCHED else MatchMethod.AUTOMATIC
            ),
            breakdown=best.breakdown,
            reason=reason,
            candidates=tuple(candidates),
        )

    def results(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str = "",
        search: str = "",
        sort: str = "confidence",
    ) -> dict[str, Any]:
        items, total = self._queries.list_results(
            provider_id=self._provider_id,
            limit=limit,
            offset=offset,
            status=status,
            search=search,
            sort=sort,
        )
        return {
            "count": total,
            "limit": max(1, min(int(limit), 500)),
            "offset": max(0, int(offset)),
            "items": items,
        }

    def result(self, external_id: str) -> dict[str, Any]:
        item = self._repository.get_result_detail(self._provider_id, external_id)
        if item is None:
            raise ValueError(
                f"Matching result {self._provider_id}:{external_id} was not found."
            )
        if isinstance(item.get("candidates"), list):
            item["candidates"] = [
                candidate
                for candidate in item["candidates"]
                if candidate.get("status") != "rejected"
            ]
        return {"result": item}

    def accept(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        self._repository.accept_manual(self._provider_id, external_id, int(local_file_id))
        self._audit.append(
            AuditEvent(
                event_type="matching_manual_accept",
                entity_type="provider_track",
                entity_id=f"{self._provider_id}:{external_id}",
                status="success",
                details=f"local_file_id={int(local_file_id)}",
            )
        )
        return self.result(external_id)

    def reject(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        self._repository.reject_candidate(self._provider_id, external_id, int(local_file_id))
        self._audit.append(
            AuditEvent(
                event_type="matching_manual_reject",
                entity_type="provider_track",
                entity_id=f"{self._provider_id}:{external_id}",
                status="success",
                details=f"local_file_id={int(local_file_id)}",
            )
        )
        return self.result(external_id)
