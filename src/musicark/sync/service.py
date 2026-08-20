"""Application boundary for Controlled Sync, including v0.11.1 recovery uploads."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError, StorageError
from musicark.coverage.repository import CoverageRepository
from musicark.download.service import DownloadService, DownloadServiceError
from musicark.recovery.managed_playlists import ManagedPlaylistError, ManagedPlaylistService
from musicark.recovery.models import RecoveryState
from musicark.recovery.service import RecoveryService
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository
from musicark.upload.batch_service import YandexBatchUploadError, YandexBatchUploadService
from musicark.upload.yandex_service import YandexSingleTrackUploadService

from .models import (
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
    SyncPlan,
    SyncPlanStatus,
    SyncScopeType,
)
from .planner import DOWNLOAD_PROVIDER, PLANNER_VERSION, SOURCE_PROVIDER, SyncPlanner, SyncPlannerError


class SyncServiceError(MusicArkError):
    def __init__(self, message: str, *, code: str = "sync_error") -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SyncService:
    """Coordinate immutable planning, revalidation, download enqueue and safe recovery upload."""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        database_path: Path | None = None,
        download_service: DownloadService | None = None,
        single_upload_service: YandexSingleTrackUploadService | None = None,
        batch_upload_service: YandexBatchUploadService | None = None,
        recovery_service: RecoveryService | None = None,
        managed_playlist_service: ManagedPlaylistService | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._coverage = CoverageRepository(self._database_path)
        self._storage = SyncStorageRepository(self._database_path)
        self._downloads = DownloadStorageRepository(self._database_path)
        self._local = LocalLibraryStorageRepository(self._database_path)
        self._download = download_service or DownloadService(base_dir=base_dir, database_path=self._database_path)
        self._recovery = recovery_service or RecoveryService(self._database_path)
        self._managed = managed_playlist_service or ManagedPlaylistService(
            self._database_path, base_dir=base_dir
        )
        self._single_upload = single_upload_service or YandexSingleTrackUploadService(base_dir=base_dir)
        self._batch_upload = batch_upload_service or YandexBatchUploadService(
            base_dir=base_dir,
            database_path=self._database_path,
            single_track_service=self._single_upload,
        )
        self._planner = SyncPlanner(
            self._database_path,
            base_dir,
            recovery_service=self._recovery,
        )
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    # ---- Read/application API ---------------------------------------------
    def scopes(self) -> dict[str, Any]:
        collections = self._coverage.collections(provider_id=SOURCE_PROVIDER)
        items: list[dict[str, Any]] = [{"type": "all", "id": None, "title": "Вся библиотека"}]
        for item in collections:
            kind = str(item.get("type") or "")
            collection_id = str(item.get("id") or "")
            if collection_id == "liked":
                items.append({"type": "liked", "id": "liked", "title": "Мне нравится"})
            elif kind == "playlist":
                items.append(
                    {
                        "type": "playlist",
                        "id": collection_id,
                        "title": str(item.get("title") or collection_id),
                    }
                )
        return {"items": items}

    def target(self) -> dict[str, Any]:
        return self._download.settings()

    def set_target(self, path: str) -> dict[str, Any]:
        try:
            return self._download.set_target(path)
        except DownloadServiceError as exc:
            raise SyncServiceError(str(exc), code=exc.code) from exc

    def create_plan(self, *, scope_type: str = "all", scope_id: str | None = None) -> dict[str, Any]:
        target = self._download.settings()
        try:
            plan = self._planner.build_plan(
                scope_type=scope_type,
                scope_id=scope_id,
                target_root_id=int(target["rootId"]) if target.get("targetConfigured") else None,
                target_folder=str(target["targetPath"]) if target.get("targetConfigured") else None,
            )
        except SyncPlannerError as exc:
            raise SyncServiceError(str(exc), code="invalid_scope") from exc
        return self._plan_payload(plan)

    def plan(self, plan_id: str, *, refresh_stale: bool = True) -> dict[str, Any]:
        plan = self._storage.get_plan(plan_id)
        if refresh_stale:
            plan = self._refresh_staleness(plan)
        return self._plan_payload(plan)

    def current(self) -> dict[str, Any]:
        plan_id = self._storage.latest_plan_id()
        return {"plan": self.plan(plan_id) if plan_id else None}

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        plans = self._storage.list_plans(limit=limit)
        items = []
        for plan in plans:
            if plan.status == SyncPlanStatus.PLANNED and not plan.is_legacy:
                plan = self._refresh_staleness(plan)
            items.append(
                {
                    "id": plan.id,
                    "createdAt": plan.created_at,
                    "scopeType": plan.scope_type.value,
                    "scopeId": plan.scope_id,
                    "scopeLabel": self._scope_label(plan),
                    "status": plan.status.value,
                    "operationCount": int(plan.summary.get("operationCount", len(plan.operations))),
                    "legacy": plan.is_legacy,
                }
            )
        return {"items": items}

    def recovery(self, *, filter_name: str = "all", limit: int = 500, offset: int = 0) -> dict[str, Any]:
        return self._recovery.payload(filter_name=filter_name, limit=limit, offset=offset)

    def managed_playlists(self) -> dict[str, Any]:
        return self._managed.state()

    def set_action(self, *, external_id: str, action: str) -> dict[str, Any]:
        clean = str(action).strip().casefold()
        if clean not in {"wanted", "ignored"}:
            raise SyncServiceError("Action must be wanted or ignored.", code="invalid_action")
        value = self._coverage.set_action(
            provider_id=SOURCE_PROVIDER,
            external_id=str(external_id).strip(),
            action=clean,
        )
        return {"externalId": str(external_id), "action": value}

    def cancel(self, plan_id: str) -> dict[str, Any]:
        try:
            self._storage.cancel_plan(plan_id)
        except StorageError as exc:
            raise SyncServiceError(str(exc), code="invalid_state") from exc
        self._audit_event("sync_plan_cancelled", plan_id, "success", {})
        return self.plan(plan_id, refresh_stale=False)

    # ---- Apply -------------------------------------------------------------
    def apply(
        self,
        plan_id: str,
        *,
        confirm: bool,
        rights_confirmed: bool = False,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise SyncServiceError("Apply Sync Plan requires explicit confirmation.", code="confirmation_required")
        plan = self._storage.get_plan(plan_id)
        if plan.is_legacy or plan.planner_version != PLANNER_VERSION:
            raise SyncServiceError(
                "Legacy / unsupported sync plans cannot be applied by the current planner.",
                code="legacy_plan_unsupported",
            )
        if plan.status == SyncPlanStatus.CANCELLED:
            raise SyncServiceError("Cancelled plan cannot be applied.", code="invalid_state")
        if plan.status == SyncPlanStatus.APPLIED:
            return {"plan": self._plan_payload(plan), "result": plan.result, "repeated": True}

        plan = self._refresh_staleness(plan)
        if plan.status == SyncPlanStatus.STALE:
            raise SyncServiceError(
                "Library state changed after plan creation. Create a new plan before applying.",
                code="stale_plan",
            )

        pending_downloads = [
            operation
            for operation in plan.operations
            if operation.operation_type == SyncOperationType.ENQUEUE_DOWNLOAD
            and operation.status == SyncOperationStatus.PENDING
        ]
        pending_uploads = [
            operation
            for operation in plan.operations
            if operation.operation_type == SyncOperationType.UPLOAD_LOCAL_TO_YANDEX
            and operation.status == SyncOperationStatus.PENDING
        ]
        if pending_uploads and rights_confirmed is not True:
            raise SyncServiceError(
                "Upload operations require explicit upload-rights confirmation.",
                code="rights_confirmation_required",
            )

        if pending_downloads:
            target = self._download.settings()
            if not target.get("targetConfigured"):
                raise SyncServiceError("Выберите папку для загрузок.", code="target_required")
            current_root = int(target["rootId"])
            current_folder = str(target["targetPath"])
            if current_root != plan.target_root_id or current_folder != plan.target_folder:
                self._mark_stale(plan, reason="download_target_changed")
                raise SyncServiceError(
                    "Download target changed after plan creation. Create a new plan.",
                    code="stale_plan",
                )

        self._audit_event("sync_plan_apply_started", plan.id, "success", {})
        download_result = self._apply_downloads(plan)
        upload_result = self._apply_uploads(plan, pending_uploads) if pending_uploads else self._empty_upload_result()

        hard_failures = int(download_result["failed"]) + int(upload_result["failed"])
        uncertain = int(upload_result["deliveryUnknown"]) + int(upload_result["ambiguous"])
        status = SyncPlanStatus.APPLIED if hard_failures == 0 and uncertain == 0 else SyncPlanStatus.PARTIALLY_APPLIED
        applied_at = _now()
        result = {
            # Legacy top-level fields stay available for v0.8/v0.9 UI/tests.
            "enqueued": download_result["enqueued"],
            "skipped": download_result["skipped"] + upload_result["skipped"],
            "failed": hard_failures,
            "taskIds": download_result["taskIds"],
            "items": download_result["items"],
            "downloadsAutoStarted": False,
            "downloads": download_result,
            "uploads": upload_result,
        }
        self._storage.update_plan_state(plan.id, status=status, applied_at=applied_at, result=result)
        self._audit_event(
            "sync_plan_apply_finished",
            plan.id,
            "success" if status == SyncPlanStatus.APPLIED else "partial",
            {
                "downloadsEnqueued": download_result["enqueued"],
                "downloadsFailed": download_result["failed"],
                "uploadsVerified": upload_result["verified"],
                "uploadsFailed": upload_result["failed"],
                "uploadsDeliveryUnknown": upload_result["deliveryUnknown"],
            },
        )
        return {"plan": self.plan(plan.id, refresh_stale=False), "result": result, "repeated": False}

    def _apply_downloads(self, plan: SyncPlan) -> dict[str, Any]:
        enqueued = 0
        skipped = 0
        failed = 0
        task_ids: list[str] = []
        items: list[dict[str, Any]] = []
        for operation in plan.operations:
            if operation.operation_type != SyncOperationType.ENQUEUE_DOWNLOAD or operation.operation_id is None:
                continue
            if operation.status == SyncOperationStatus.ENQUEUED:
                result = dict(operation.result)
                if result.get("task_id"):
                    task_ids.append(str(result["task_id"]))
                items.append({"externalId": operation.entity_id, **result})
                continue
            if operation.status == SyncOperationStatus.SKIPPED and operation.reason == "already_queued":
                skipped += 1
                result = dict(operation.result)
                if result.get("task_id"):
                    task_ids.append(str(result["task_id"]))
                items.append({"externalId": operation.entity_id, **result})
                continue
            if operation.status != SyncOperationStatus.PENDING:
                continue
            result = self._apply_download_operation(operation)
            state = str(result.get("state") or "failed")
            if state == "enqueued":
                enqueued += 1
                if result.get("task_id"):
                    task_ids.append(str(result["task_id"]))
            elif state == "skipped":
                skipped += 1
                if result.get("task_id"):
                    task_ids.append(str(result["task_id"]))
            else:
                failed += 1
            items.append({"externalId": operation.entity_id, **result})
        return {
            "enqueued": enqueued,
            "skipped": skipped,
            "failed": failed,
            "taskIds": [value for value in task_ids if value],
            "items": items,
        }

    @staticmethod
    def _empty_upload_result() -> dict[str, Any]:
        return {
            "total": 0,
            "verified": 0,
            "processing": 0,
            "deliveryUnknown": 0,
            "failed": 0,
            "unsupported": 0,
            "ambiguous": 0,
            "skipped": 0,
            "items": [],
        }

    def _apply_uploads(
        self,
        plan: SyncPlan,
        operations: list[SyncOperation],
    ) -> dict[str, Any]:
        aggregate = self._empty_upload_result()
        recovery = self._recovery.by_external_ids(operation.entity_id for operation in operations)
        groups: dict[tuple[str, str], list[SyncOperation]] = defaultdict(list)

        for operation in operations:
            assert operation.operation_id is not None
            current = recovery.get(operation.entity_id)
            role = str(operation.metadata.get("targetRole") or "")
            target_kind = str(operation.metadata.get("targetPlaylistKind") or "")
            local_file_id = int(operation.metadata.get("localFileId") or 0)
            reason: str | None = None
            if current is None:
                reason = "recovery_state_missing"
            elif current.local_file_id != local_file_id:
                reason = "local_match_changed"
            elif role == "unavailable" and current.state != RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE:
                reason = "provider_availability_changed"
            elif role == "censored" and current.state != RecoveryState.CENSORED_ORIGINAL_AVAILABLE:
                reason = "content_labels_changed"
            elif not target_kind:
                reason = "managed_playlist_missing"
            else:
                local = self._local.get_track(local_file_id)
                if local is None:
                    reason = "local_file_missing"
                elif str(local.get("extension") or "").casefold() != ".mp3":
                    reason = "unsupported_format"
                else:
                    path = Path(str(local.get("path") or ""))
                    if not path.exists() or not path.is_file():
                        reason = "local_file_missing"
            if reason is not None:
                result = {"state": "skipped", "reason": reason, "localFileId": local_file_id}
                self._storage.update_operation_state(
                    operation.operation_id, status=SyncOperationStatus.SKIPPED, result=result
                )
                aggregate["skipped"] += 1
                aggregate["items"].append({"externalId": operation.entity_id, **result})
                continue
            groups[(role, target_kind)].append(operation)

        for (role, target_kind), group in groups.items():
            try:
                current_kind, _ = self._managed.validate_role(role)
            except ManagedPlaylistError:
                for operation in group:
                    result = {"state": "skipped", "reason": "managed_playlist_invalid"}
                    self._storage.update_operation_state(
                        int(operation.operation_id or 0), status=SyncOperationStatus.SKIPPED, result=result
                    )
                    aggregate["skipped"] += 1
                    aggregate["items"].append({"externalId": operation.entity_id, **result})
                continue
            if current_kind != target_kind:
                for operation in group:
                    result = {"state": "skipped", "reason": "managed_playlist_changed"}
                    self._storage.update_operation_state(
                        int(operation.operation_id or 0), status=SyncOperationStatus.SKIPPED, result=result
                    )
                    aggregate["skipped"] += 1
                    aggregate["items"].append({"externalId": operation.entity_id, **result})
                continue

            local_ids = [int(operation.metadata["localFileId"]) for operation in group]
            self._audit_event(
                "sync_upload_started",
                plan.id,
                "success",
                {"role": role, "playlistKind": target_kind, "count": len(local_ids)},
            )
            try:
                batch = self._batch_upload.execute(
                    local_file_ids=local_ids,
                    playlist_kind=target_kind,
                    confirm=True,
                    rights_confirmed=True,
                    batch_id=f"sync-{uuid4()}",
                    allow_stale_reupload=True,
                )
            except YandexBatchUploadError:
                batch = {"items": []}

            batch_by_local = {
                int(item.get("localFileId") or 0): item
                for item in batch.get("items", [])
                if isinstance(item, dict) and int(item.get("localFileId") or 0) > 0
            }
            for operation in group:
                local_file_id = int(operation.metadata["localFileId"])
                item = batch_by_local.get(local_file_id)
                if item is None:
                    state = "failed"
                    safe_result = {"state": "failed", "reason": "batch_execution_failed"}
                else:
                    state = str(item.get("status") or item.get("result", {}).get("state") or "failed")
                    raw_result = item.get("result") if isinstance(item.get("result"), dict) else {}
                    safe_result = dict(raw_result)
                    safe_result.setdefault("state", state)
                op_status = {
                    "verified": SyncOperationStatus.VERIFIED,
                    "processing": SyncOperationStatus.PROCESSING,
                    "delivery_unknown": SyncOperationStatus.DELIVERY_UNKNOWN,
                    "skipped": SyncOperationStatus.SKIPPED,
                }.get(state, SyncOperationStatus.FAILED)
                self._storage.update_operation_state(
                    int(operation.operation_id or 0), status=op_status, result=safe_result
                )
                key = {
                    "verified": "verified",
                    "processing": "processing",
                    "delivery_unknown": "deliveryUnknown",
                    "unsupported": "unsupported",
                    "ambiguous": "ambiguous",
                    "skipped": "skipped",
                }.get(state, "failed")
                aggregate[key] += 1
                aggregate["items"].append(
                    {
                        "externalId": operation.entity_id,
                        "localFileId": local_file_id,
                        "role": role,
                        "playlistKind": target_kind,
                        **safe_result,
                    }
                )
                event_type = {
                    "verified": "sync_upload_verified",
                    "delivery_unknown": "sync_upload_delivery_unknown",
                }.get(state, "sync_upload_failed" if state in {"failed", "unsupported", "ambiguous"} else None)
                if event_type:
                    self._audit_event(
                        event_type,
                        str(operation.operation_id),
                        "success" if state == "verified" else state,
                        {
                            "externalTrackId": operation.entity_id,
                            "localFileId": local_file_id,
                            "playlistKind": target_kind,
                            "role": role,
                            "resultState": state,
                        },
                    )

        aggregate["total"] = sum(
            int(aggregate[key])
            for key in (
                "verified",
                "processing",
                "deliveryUnknown",
                "failed",
                "unsupported",
                "ambiguous",
                "skipped",
            )
        )
        return aggregate

    def _apply_download_operation(self, operation: SyncOperation) -> dict[str, Any]:
        assert operation.operation_id is not None
        external_id = operation.entity_id
        current = self._coverage.get_track(provider_id=SOURCE_PROVIDER, external_id=external_id)
        if current is None:
            return self._skip_operation(operation, "track_not_in_active_library")
        coverage = str(current.get("coverageStatus") or "")
        action = str(current.get("userAction") or "unreviewed")
        if coverage == "covered":
            return self._skip_operation(operation, "already_covered")
        if coverage != "missing":
            return self._skip_operation(operation, f"coverage_{coverage or 'unknown'}")
        if action != "wanted":
            return self._skip_operation(operation, f"action_{action}")

        active = self._downloads.find_active(DOWNLOAD_PROVIDER, external_id)
        if active is not None:
            return self._skip_operation(operation, "already_queued", task_id=active.id)

        try:
            payload = self._download.enqueue(external_id, provider_id=SOURCE_PROVIDER)
            task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
            task_id = str(task.get("id") or "")
            if not bool(payload.get("created")):
                return self._skip_operation(operation, "already_queued", task_id=task_id or None)
            result = {"state": "enqueued", "reason": "queued", "task_id": task_id}
            self._storage.update_operation_state(
                operation.operation_id, status=SyncOperationStatus.ENQUEUED, result=result
            )
            self._audit_event(
                "sync_operation_enqueued",
                str(operation.operation_id),
                "success",
                {"external_id": external_id, "task_id": task_id},
            )
            return result
        except DownloadServiceError as exc:
            result = {"state": "failed", "reason": exc.code, "message": str(exc)}
            self._storage.update_operation_state(
                operation.operation_id, status=SyncOperationStatus.FAILED, result=result
            )
            self._audit_event(
                "sync_operation_skipped",
                str(operation.operation_id),
                "failed",
                {"external_id": external_id, "reason": exc.code},
            )
            return result

    def _skip_operation(
        self, operation: SyncOperation, reason: str, *, task_id: str | None = None
    ) -> dict[str, Any]:
        assert operation.operation_id is not None
        result: dict[str, Any] = {"state": "skipped", "reason": reason}
        if task_id:
            result["task_id"] = task_id
        self._storage.update_operation_state(
            operation.operation_id, status=SyncOperationStatus.SKIPPED, result=result
        )
        self._audit_event(
            "sync_operation_skipped",
            str(operation.operation_id),
            "success",
            {"external_id": operation.entity_id, "reason": reason, "task_id": task_id},
        )
        return result

    # ---- Staleness ---------------------------------------------------------
    def _refresh_staleness(self, plan: SyncPlan) -> SyncPlan:
        if plan.is_legacy or plan.status not in {SyncPlanStatus.PLANNED, SyncPlanStatus.PARTIALLY_APPLIED}:
            return plan
        target = self._download.settings()
        root_id = int(target["rootId"]) if target.get("targetConfigured") else None
        folder = str(target["targetPath"]) if target.get("targetConfigured") else None
        try:
            fingerprint = self._planner.current_fingerprint(
                scope_type=plan.scope_type,
                scope_id=plan.scope_id,
                target_root_id=root_id,
                target_folder=folder,
            )
        except SyncPlannerError:
            return self._mark_stale(plan, reason="scope_no_longer_active")
        if fingerprint != plan.input_fingerprint:
            return self._mark_stale(plan, reason="input_fingerprint_changed")
        return plan

    def _mark_stale(self, plan: SyncPlan, *, reason: str) -> SyncPlan:
        if plan.status in {SyncPlanStatus.PLANNED, SyncPlanStatus.PARTIALLY_APPLIED}:
            self._storage.update_plan_state(plan.id, status=SyncPlanStatus.STALE)
            self._audit_event("sync_plan_stale", plan.id, "success", {"reason": reason})
            plan = self._storage.get_plan(plan.id)
        return plan

    # ---- Serialization -----------------------------------------------------
    def _plan_payload(self, plan: SyncPlan) -> dict[str, Any]:
        return {
            "id": plan.id,
            "createdAt": plan.created_at,
            "plannerVersion": plan.planner_version,
            "scopeType": plan.scope_type.value,
            "scopeId": plan.scope_id,
            "scopeLabel": self._scope_label(plan),
            "targetRootId": plan.target_root_id,
            "targetFolder": plan.target_folder,
            "inputFingerprint": plan.input_fingerprint,
            "status": plan.status.value,
            "appliedAt": plan.applied_at,
            "legacy": plan.is_legacy,
            "summary": plan.summary,
            "result": plan.result,
            "operations": [self._operation_payload(value) for value in plan.operations],
        }

    @staticmethod
    def _operation_payload(operation: SyncOperation) -> dict[str, Any]:
        return {
            "id": operation.operation_id,
            "type": operation.operation_type.value,
            "externalId": operation.entity_id,
            "reason": operation.reason,
            "status": operation.status.value,
            "dangerous": operation.is_dangerous,
            "metadata": operation.metadata,
            "result": operation.result,
        }

    def _scope_label(self, plan: SyncPlan) -> str:
        if plan.scope_type == SyncScopeType.ALL:
            return "Вся библиотека"
        if plan.scope_type == SyncScopeType.LIKED:
            return "Мне нравится"
        if plan.scope_type == SyncScopeType.LEGACY:
            return "Legacy / unsupported plan"
        for item in self._coverage.collections(provider_id=SOURCE_PROVIDER):
            if str(item.get("id") or "") == str(plan.scope_id or ""):
                return str(item.get("title") or plan.scope_id or "Yandex Playlist")
        return str(plan.scope_id or "Yandex Playlist")

    def _audit_event(
        self, event_type: str, entity_id: str, status: str, details: dict[str, Any]
    ) -> None:
        safe = {
            key: value
            for key, value in details.items()
            if key not in {"path", "filePath", "token", "uid", "Authorization", "Cookie"}
        }
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="sync_plan" if event_type.startswith("sync_plan") else "sync_operation",
                entity_id=entity_id,
                status=status,
                details=json.dumps(safe, ensure_ascii=False, sort_keys=True)[:16000],
            )
        )
