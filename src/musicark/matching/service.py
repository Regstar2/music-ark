"""Application-level orchestration for MusicArk v0.5/v0.8 matching."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from musicark.core.config import load_config
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository
from .candidates import CandidateGenerator
from .fingerprints import provider_fingerprint
from .indexer import LocalMatchIndex
from .input import MatchingInputRepository
from .manual_state import ManualMatchState
from .models import MatchDecision, MatchMethod, MatchStatus, ScoredCandidate
from .policy import AMBIGUITY_MARGIN, AUTO_MATCH_THRESHOLD, CONFLICT_THRESHOLD, MATCHER_VERSION
from .result_queries import MatchingResultQueries
from .scope import MatchingScopeState
from .scoring import MatchScorer


class MatchingService:
    """Offline matching over the currently selected Yandex collection and Local Library."""

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
        self._manual_state = ManualMatchState(self._database_path)
        self._scope = MatchingScopeState(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    @staticmethod
    def _provider_fingerprint(provider: dict[str, Any]) -> str:
        return provider_fingerprint(
            str(provider["provider_id"]),
            str(provider["external_id"]),
            dict(provider["payload"]),
        )

    def _collection(self, collection_id: str | None) -> str:
        return self._scope.resolve_collection(collection_id, self._provider_id)

    def _providers(self, collection_id: str) -> list[dict[str, Any]]:
        providers = self._repository.list_provider_track_candidates(self._provider_id)
        scoped_ids = self._scope.external_ids(
            provider_id=self._provider_id,
            collection_id=collection_id,
        )
        if scoped_ids is None:
            return providers
        return [
            item
            for item in providers
            if str(item.get("external_id") or "") in scoped_ids
        ]

    def summary(self, *, collection_id: str | None = None) -> dict[str, Any]:
        self._input.sync_provider_tracks(self._provider_id)
        collection = self._collection(collection_id)
        return self._scope.summary(
            self._repository,
            provider_id=self._provider_id,
            collection_id=collection,
        )

    def run(self, *, collection_id: str | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        self._input.sync_provider_tracks(self._provider_id)
        collection = self._collection(collection_id)
        stale = self._scope.invalidate_non_library_matches()
        index_updates = self._local_index.refresh()
        # Keep the existing global fingerprint contract so v0.6 Coverage and v0.7
        # Download freshness remain compatible. Root ownership is enforced separately.
        local_fingerprint = self._repository.local_library_fingerprint()
        providers = self._providers(collection)
        provider_identity_count = len(providers)
        generator = CandidateGenerator(
            self._repository,
            database_path=self._database_path,
        )
        batch: list[MatchDecision] = []
        unchanged = 0
        manual_stale = 0

        for provider in providers:
            provider_id = str(provider["provider_id"])
            external_id = str(provider["external_id"])
            provider_fp = self._provider_fingerprint(provider)
            existing = self._repository.get_existing_result(provider_id, external_id)
            if existing and existing.get("manual"):
                if self._manual_state.mark_if_stale(
                    provider_id,
                    external_id,
                    existing,
                    provider_fp,
                ):
                    manual_stale += 1
                else:
                    unchanged += 1
                continue
            if (
                existing
                and int(existing.get("matcher_version") or 0) == MATCHER_VERSION
                and existing.get("provider_fingerprint") == provider_fp
                and existing.get("local_fingerprint") == local_fingerprint
            ):
                unchanged += 1
                continue

            rejected = self._repository.rejected_local_ids(provider_id, external_id)
            local_candidates = generator.generate(provider, excluded_local_ids=rejected)
            scored = sorted(
                (self._scorer.score(provider, local) for local in local_candidates),
                key=lambda item: (self._is_exact_identity(item), item.confidence),
                reverse=True,
            )
            batch.append(
                self._decide(
                    provider,
                    provider_fingerprint=provider_fp,
                    local_fingerprint=local_fingerprint,
                    candidates=scored,
                )
            )
            if len(batch) >= 250:
                self._repository.persist_batch(batch)
                batch.clear()
        self._repository.persist_batch(batch)

        summary = self._scope.summary(
            self._repository,
            provider_id=self._provider_id,
            collection_id=collection,
        )
        duration = max(0.0, time.perf_counter() - started)
        result = {
            "total": summary["processed"],
            "providerIdentities": provider_identity_count,
            "collectionId": collection,
            "matched": summary["matched"],
            "conflicts": summary["conflicts"],
            "unmatched": summary["unmatched"],
            "unchanged": unchanged,
            "manualStale": manual_stale,
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
                    f"collection={collection or 'all'} matched={result['matched']} "
                    f"conflicts={result['conflicts']} unmatched={result['unmatched']} "
                    f"unchanged={unchanged} manual_stale={manual_stale} "
                    f"comparisons={generator.comparison_count}"
                ),
            )
        )
        return result

    @staticmethod
    def _is_exact_identity(candidate: ScoredCandidate) -> bool:
        return (
            candidate.method is MatchMethod.EXACT_ID
            and float(candidate.breakdown.get("exact_id") or 0.0) >= 1.0
        )

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

        exact_candidates = [
            candidate
            for candidate in candidates
            if MatchingService._is_exact_identity(candidate)
        ]
        best = exact_candidates[0] if exact_candidates else candidates[0]
        if len(exact_candidates) == 1:
            status = MatchStatus.MATCHED
            reason = "exact_provider_identity"
        elif len(exact_candidates) > 1:
            status = MatchStatus.CONFLICT
            reason = "ambiguous_exact_id_candidates"
        else:
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
        collection_id: str | None = None,
    ) -> dict[str, Any]:
        collection = self._collection(collection_id)
        effective_search = self._scope.clean_search(search)
        items, total = self._queries.list_results(
            provider_id=self._provider_id,
            limit=limit,
            offset=offset,
            status=status,
            search=effective_search,
            sort=sort,
            collection_id=collection,
        )
        return {
            "count": total,
            "limit": max(1, min(int(limit), 500)),
            "offset": max(0, int(offset)),
            "collectionId": collection,
            "search": effective_search,
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
        item["stale"] = self._manual_state.is_stale_reason(str(item.get("reason") or ""))
        return {"result": item}

    def accept(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        self._scope.assert_local_file_allowed(int(local_file_id))
        self._repository.accept_manual(self._provider_id, external_id, int(local_file_id))
        self._manual_state.store_reference(self._provider_id, external_id)
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
