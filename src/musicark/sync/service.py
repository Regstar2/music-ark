"""Application boundary for MusicArk v0.8 Controlled Sync."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError, StorageError
from musicark.coverage.repository import CoverageRepository
from musicark.download.service import DownloadService, DownloadServiceError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository

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
    """Coordinate planning, staleness validation and safe enqueue-only Apply."""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        database_path: Path | None = None,
        download_service: DownloadService | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._coverage = CoverageRepository(self._database_path)
        self._storage = SyncStorageRepository(self._database_path)
        self._downloads = DownloadStorageRepository(self._database_path)
        self._download = download_service or DownloadService(
            base_dir=base_dir, database_path=self._database_path
        )
        self._planner = SyncPlanner(self._database_path, base_dir)
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    # ---- Read/application API ------------------------------------------------
    def scopes(self) -> dict[str, Any]:
        collections = self._coverage.collections(provider_id=SOURCE_PROVIDER)
        items: list[dict[str, Any]] = [
            {"type": "all", "id": None, "title": "Вся библиотека"}
        ]
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

    # ---- Apply ---------------------------------------------------------------
    def apply(self, plan_id: str, *, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise SyncServiceError(
                "Apply Sync Plan requires explicit confirmation.", code="confirmation_required"
            )
        plan = self._storage.get_plan(plan_id)
        if plan.is_legacy or plan.planner_version != PLANNER_VERSION:
            raise SyncServiceError(
                "Legacy / unsupported sync plans cannot be applied by v0.8.",
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
        enqueued = 0
        skipped = 0
        failed = 0
        task_ids: list[str] = []
        items: list[dict[str, Any]] = []

        for operation in plan.operations:
            if operation.operation_type != SyncOperationType.ENQUEUE_DOWNLOAD:
                continue
            if operation.operation_id is None:
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

            result = self._apply_download_operation(operation)
            state = str(result.get("state") or "failed")
            if state == "enqueued":
                enqueued += 1
                task_ids.append(str(result.get("task_id") or ""))
            elif state == "skipped":
                skipped += 1
                if result.get("task_id"):
                    task_ids.append(str(result["task_id"]))
            else:
                failed += 1
            items.append({"externalId": operation.entity_id, **result})

        status = SyncPlanStatus.APPLIED if failed == 0 else SyncPlanStatus.PARTIALLY_APPLIED
        applied_at = _now()
        result = {
            "enqueued": enqueued,
            "skipped": skipped,
            "failed": failed,
            "taskIds": [value for value in task_ids if value],
            "items": items,
            "downloadsAutoStarted": False,
        }
        self._storage.update_plan_state(
            plan.id, status=status, applied_at=applied_at, result=result
        )
        self._audit_event(
            "sync_plan_apply_finished",
            plan.id,
            "success" if failed == 0 else "partial",
            {"enqueued": enqueued, "skipped": skipped, "failed": failed},
        )
        return {"plan": self.plan(plan.id, refresh_stale=False), "result": result, "repeated": False}

    def _apply_download_operation(self, operation: SyncOperation) -> dict[str, Any]:
        assert operation.operation_id is not None
        external_id = operation.entity_id
        current = self._coverage.get_track(
            provider_id=SOURCE_PROVIDER, external_id=external_id
        )
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
                {"plan_operation": operation.operation_id, "external_id": external_id, "task_id": task_id},
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

    # ---- Staleness -----------------------------------------------------------
    def _refresh_staleness(self, plan: SyncPlan) -> SyncPlan:
        if plan.is_legacy or plan.status not in {
            SyncPlanStatus.PLANNED,
            SyncPlanStatus.PARTIALLY_APPLIED,
        }:
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

    # ---- Serialization -------------------------------------------------------
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
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="sync_plan" if event_type.startswith("sync_plan") else "sync_operation",
                entity_id=entity_id,
                status=status,
                details=json.dumps(details, ensure_ascii=False, sort_keys=True)[:16000],
            )
        )
