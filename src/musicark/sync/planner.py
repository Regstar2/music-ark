"""Sync planner implementation for v0.8."""

from __future__ import annotations

from pathlib import Path

from musicark.core.config import load_config
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.matching_storage import MatchingStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository

from .models import SyncOperation, SyncOperationType, SyncPlan


class SyncPlanner:
    """Builds dry-run sync operations by comparing provider/local/matching state."""

    def __init__(self, database_path: Path, base_dir: Path | None = None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir
        self._matching_storage = MatchingStorageRepository(database_path)
        self._sync_storage = SyncStorageRepository(database_path)
        self._audit = AuditLogRepository(database_path)

    def build_plan(self, dry_run: bool = True) -> SyncPlan:
        cfg = load_config(self._base_dir)
        experimental_upload = cfg.experimental_yandex_upload

        links_by_external: dict[str, int] = {}
        if experimental_upload:
            for row in self._matching_storage.list_track_links_for_provider("yandex_music"):
                links_by_external[str(row["source_external_id"])] = int(row["local_file_id"])

        provider_tracks = self._matching_storage.list_provider_track_candidates()
        local_files = self._matching_storage.list_local_audio_files()
        operations: list[SyncOperation] = []

        local_by_external_id: dict[str, dict] = {}
        for item in local_files:
            path = str(item["path"])
            name = Path(path).stem
            if name.startswith("yandex_"):
                external_id = name[len("yandex_") :]
                local_by_external_id[external_id] = item

        for candidate in provider_tracks:
            payload = candidate["payload"]
            external_id = candidate["external_id"]
            availability = payload.get("availability")
            has_local_copy = external_id in local_by_external_id

            if availability == "unavailable":
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.MARK_UNAVAILABLE,
                        entity_id=external_id,
                        reason="remote_unavailable",
                        confidence=1.0,
                        is_dangerous=False,
                    )
                )
                loc_id = links_by_external.get(external_id)
                if experimental_upload and loc_id is not None:
                    meta = {"local_file_id": loc_id, "original_external_id": external_id}
                    operations.append(
                        SyncOperation(
                            operation_type=SyncOperationType.UPLOAD_CANDIDATE,
                            entity_id=external_id,
                            reason="remote_unavailable_matched_local_for_experimental_restore",
                            confidence=0.55,
                            is_dangerous=True,
                            metadata=meta,
                        )
                    )
                    operations.append(
                        SyncOperation(
                            operation_type=SyncOperationType.REPLACE_CANDIDATE,
                            entity_id=external_id,
                            reason="post_upload_hypothetical_playlist_catalog_replace_placeholder",
                            confidence=0.40,
                            is_dangerous=True,
                            metadata=meta,
                        )
                    )
                continue

            if not has_local_copy:
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.DOWNLOAD_TRACK,
                        entity_id=external_id,
                        reason="missing_local_copy",
                        confidence=0.95,
                        is_dangerous=False,
                    )
                )
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.CREATE_DOWNLOAD_TASK,
                        entity_id=external_id,
                        reason="create_download_task_for_missing_local",
                        confidence=0.95,
                        is_dangerous=False,
                        metadata={
                            "task_type": "yandex_download",
                            "provider_id": "yandex_music_download",
                            "source_id": external_id,
                        },
                    )
                )
            else:
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.LINK_LOCAL,
                        entity_id=external_id,
                        reason="local_copy_exists",
                        confidence=0.90,
                        is_dangerous=False,
                        metadata={"local_file_id": local_by_external_id[external_id]["id"]},
                    )
                )

            if payload.get("source_type") == "yandex_music" and payload.get("raw_data"):
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.UPDATE_METADATA_CANDIDATE,
                        entity_id=external_id,
                        reason="metadata_changed_candidate",
                        confidence=0.60,
                        is_dangerous=True,
                    )
                )

        # local-only files without yandex naming are review candidates
        for local in local_files:
            name = Path(str(local["path"])).stem
            if not name.startswith("yandex_"):
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.NEEDS_REVIEW,
                        entity_id=str(local["id"]),
                        reason="local_only_or_unmatched",
                        confidence=0.40,
                        is_dangerous=False,
                        metadata={"path": local["path"]},
                    )
                )

        summary = _summarize_operations(operations)
        plan = SyncPlan(dry_run=dry_run, operations=operations, summary=summary)
        self._sync_storage.save_plan(plan)
        self._audit.append(
            AuditEvent(
                event_type="sync_plan_created",
                entity_type="sync_plan",
                entity_id=plan.id,
                status="success",
                details=f"operations={len(operations)} dry_run={dry_run}",
            )
        )
        return plan

    def show_plan(self, plan_id: str) -> SyncPlan:
        return self._sync_storage.get_plan(plan_id)

    def cancel_plan(self, plan_id: str) -> None:
        self._sync_storage.cancel_plan(plan_id)
        self._audit.append(
            AuditEvent(
                event_type="sync_plan_cancelled",
                entity_type="sync_plan",
                entity_id=plan_id,
                status="success",
                details="plan status changed to cancelled",
            )
        )


def _summarize_operations(operations: list[SyncOperation]) -> dict[str, int]:
    result: dict[str, int] = {}
    for operation in operations:
        key = operation.operation_type.value
        result[key] = result.get(key, 0) + 1
    result["total"] = len(operations)
    result["dangerous"] = sum(1 for op in operations if op.is_dangerous)
    return result
