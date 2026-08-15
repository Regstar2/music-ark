"""Application orchestration for MusicArk v0.6 Library Coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from musicark.core.config import load_config
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository

from .repository import CoverageRepository


class LibraryCoverageService:
    """Derived local coverage over active cached provider identities.

    This service never performs matching. It consumes v0.5 matching state, the
    v0.5.1 variant layer, active provider collection membership, and Local Library.
    """

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
        self._repository = CoverageRepository(self._database_path)
        self._matching_repository = MatchingStorageRepository(self._database_path)
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def summary(self, *, collection_id: str = "") -> dict[str, Any]:
        return self._repository.summary(
            provider_id=self._provider_id,
            collection_id=collection_id,
        )

    def tracks(
        self,
        *,
        collection_id: str = "",
        status: str = "missing",
        search: str = "",
        sort: str = "artist",
        user_action: str = "",
        variant_status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        items, total = self._repository.list_tracks(
            provider_id=self._provider_id,
            collection_id=collection_id,
            status=status,
            search=search,
            sort=sort,
            user_action=user_action,
            variant_status=variant_status,
            limit=limit,
            offset=offset,
        )
        return {
            "count": total,
            "limit": max(1, min(int(limit), 500)),
            "offset": max(0, int(offset)),
            "items": items,
        }

    def track(self, external_id: str) -> dict[str, Any]:
        item = self._repository.get_track(
            provider_id=self._provider_id,
            external_id=external_id,
        )
        if item is None:
            raise ValueError(
                f"Coverage track {self._provider_id}:{external_id} was not found "
                "in the active provider library."
            )

        matching = None
        matching_status = item.get("matchingStatus")
        if matching_status:
            matching = self._matching_repository.get_result_detail(
                self._provider_id, external_id
            )
            if matching is not None and item["coverageStatus"] == "needs_review":
                # Reuse the v0.5 candidate representation rather than implementing
                # a second matching-detail model here.
                matching["candidates"] = [
                    candidate
                    for candidate in matching.get("candidates", [])
                    if candidate.get("status") != "rejected"
                ]

        return {
            "track": item,
            "matching": matching,
            "variant": (
                {
                    "status": item.get("variantStatus") or "not_checked",
                    "applicable": True,
                }
                if item["coverageStatus"] == "covered"
                else {
                    "status": None,
                    "applicable": False,
                    "reason": "no_accepted_local_identity",
                }
            ),
        }

    def collections(self) -> dict[str, Any]:
        return {
            "items": self._repository.collections(provider_id=self._provider_id)
        }

    def set_action(self, external_id: str, action: str) -> dict[str, Any]:
        clean_action = self._repository.set_action(
            provider_id=self._provider_id,
            external_id=external_id,
            action=action,
        )
        self._audit.append(
            AuditEvent(
                event_type="coverage_track_action",
                entity_type="provider_track",
                entity_id=f"{self._provider_id}:{external_id}",
                status="success",
                details=f"action={clean_action}",
            )
        )
        return {
            "providerId": self._provider_id,
            "externalId": external_id,
            "userAction": clean_action,
        }

    def set_actions(
        self, external_ids: Iterable[str], action: str
    ) -> dict[str, Any]:
        result = self._repository.set_actions(
            provider_id=self._provider_id,
            external_ids=external_ids,
            action=action,
        )
        self._audit.append(
            AuditEvent(
                event_type="coverage_bulk_action",
                entity_type="provider_track",
                entity_id=self._provider_id,
                status="success",
                details=f"action={result['action']} count={result['updated']}",
            )
        )
        return result
