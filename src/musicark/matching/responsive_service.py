"""Large-library matching orchestration with bounded progress reporting."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
import sqlite3
import time
from typing import Any

from musicark.storage.audit_log import AuditEvent

from .fingerprints import provider_fingerprint
from .policy import MATCHER_VERSION
from .responsive_candidates import ResponsiveCandidateGenerator
from .service import MatchingService

ProgressCallback = Callable[[int, int], None]
_PROGRESS_INTERVAL = 25


class ResponsiveMatchingService(MatchingService):
    """Preserve v0.5 matching semantics while removing per-identity DB setup."""

    def run(
        self,
        *,
        collection_id: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        self._input.sync_provider_tracks(self._provider_id)
        collection = self._collection(collection_id)
        stale = self._scope.invalidate_non_library_matches()
        index_updates = self._local_index.refresh()
        local_fingerprint = self._repository.local_library_fingerprint()
        providers = self._providers(collection)
        provider_identity_count = len(providers)
        batch = []
        unchanged = 0
        manual_stale = 0

        if progress is not None:
            progress(0, provider_identity_count)

        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                existing_by_id, rejected_by_id = self._preload_run_state(conn)
                generator = ResponsiveCandidateGenerator(conn)

                for index, provider in enumerate(providers, start=1):
                    try:
                        provider_id = str(provider["provider_id"])
                        external_id = str(provider["external_id"])
                        provider_fp = provider_fingerprint(
                            provider_id,
                            external_id,
                            dict(provider["payload"]),
                        )
                        existing = existing_by_id.get(external_id)
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

                        rejected = rejected_by_id.get(external_id, set())
                        local_candidates = generator.generate(
                            provider,
                            excluded_local_ids=rejected,
                        )
                        scored = sorted(
                            (self._scorer.score(provider, local) for local in local_candidates),
                            key=lambda item: item.confidence,
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
                    finally:
                        if progress is not None and (
                            index == provider_identity_count or index % _PROGRESS_INTERVAL == 0
                        ):
                            progress(index, provider_identity_count)

                self._repository.persist_batch(batch)
        except sqlite3.Error as exc:
            from musicark.core.errors import StorageError

            raise StorageError("Failed to prepare optimized matching run state.") from exc

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
                    f"comparisons={generator.comparison_count} optimized=1"
                ),
            )
        )
        return result

    def _preload_run_state(
        self,
        conn: sqlite3.Connection,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, set[int]]]:
        existing_rows = conn.execute(
            """
            SELECT external_id, local_file_id, reason, matcher_version,
                   provider_fingerprint, local_fingerprint, manual
            FROM matching_results
            WHERE provider_id=?
            """,
            (self._provider_id,),
        ).fetchall()
        existing = {
            str(row[0]): {
                "local_file_id": row[1],
                "reason": row[2],
                "matcher_version": int(row[3] or 0),
                "provider_fingerprint": row[4] or "",
                "local_fingerprint": row[5] or "",
                "manual": bool(row[6]),
            }
            for row in existing_rows
        }

        rejected_rows = conn.execute(
            """
            SELECT source_external_id, local_file_id
            FROM match_conflicts
            WHERE source_provider_id=? AND status='rejected'
            """,
            (self._provider_id,),
        ).fetchall()
        rejected: dict[str, set[int]] = {}
        for external_id, local_file_id in rejected_rows:
            rejected.setdefault(str(external_id), set()).add(int(local_file_id))
        return existing, rejected
