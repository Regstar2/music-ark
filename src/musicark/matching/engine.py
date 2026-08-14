"""Legacy-compatible facade over the v0.5 matching pipeline."""

from __future__ import annotations

from pathlib import Path

from musicark.storage.matching_storage import MatchingStorageRepository
from .service import MatchingService


class MatchingEngine:
    """Compatibility wrapper kept for older CLI/tests.

    v0.5 matching itself lives in CandidateGenerator + MatchScorer + MatchingService;
    this class intentionally no longer owns the algorithm.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._service = MatchingService(database_path=database_path)
        self._storage = MatchingStorageRepository(database_path)

    def run(self) -> dict[str, int]:
        result = self._service.run()
        return {
            "linked": int(result["matched"]),
            "conflicts": int(result["conflicts"]),
            "skipped": int(result["unmatched"]),
        }

    def list_conflicts(self) -> list[dict]:
        return self._storage.list_open_conflicts()

    def accept(self, conflict_id: int) -> None:
        self._storage.accept_conflict_by_id(conflict_id)
