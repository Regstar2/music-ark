"""Read-only Controlled Sync planner with v0.11.1 recovery upload operations."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from musicark.coverage.repository import CoverageRepository
from musicark.recovery.models import RecoveryState, RecoveryTrack
from musicark.recovery.service import RecoveryService
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.matching_storage import MatchingStorageRepository
from musicark.storage.recovery_storage import RecoveryStorageRepository
from musicark.storage.sync_storage import SyncStorageRepository

from .models import (
    SyncOperation,
    SyncOperationStatus,
    SyncOperationType,
    SyncPlan,
    SyncScopeType,
)


PLANNER_VERSION = 2
SOURCE_PROVIDER = "yandex_music"
DOWNLOAD_PROVIDER = "yandex_music_download"
_VARIANT_REVIEW = {"uncertain", "altered", "different_version"}


class SyncPlannerError(ValueError):
    pass


@dataclass(slots=True)
class _PlanInput:
    scope_type: SyncScopeType
    scope_id: str | None
    collection_id: str
    target_root_id: int | None
    target_folder: str | None
    tracks: list[dict[str, Any]]
    recovery: dict[str, RecoveryTrack]
    managed: dict[str, dict[str, Any]]
    local_fingerprint: str
    active_downloads: dict[str, str]


class SyncPlanner:
    """Build immutable dry-run plans from existing authoritative state only."""

    def __init__(
        self,
        database_path: Path,
        base_dir: Path | None = None,
        *,
        recovery_service: RecoveryService | None = None,
    ) -> None:
        self._database_path = Path(database_path)
        self._base_dir = base_dir
        self._coverage = CoverageRepository(self._database_path)
        self._matching = MatchingStorageRepository(self._database_path)
        self._storage = SyncStorageRepository(self._database_path)
        self._audit = AuditLogRepository(self._database_path)
        self._recovery = recovery_service or RecoveryService(self._database_path)
        self._recovery_storage = RecoveryStorageRepository(self._database_path)

    def build_plan(
        self,
        dry_run: bool = True,
        *,
        scope_type: str | SyncScopeType = SyncScopeType.ALL,
        scope_id: str | None = None,
        target_root_id: int | None = None,
        target_folder: str | None = None,
    ) -> SyncPlan:
        data = self._read_inputs(
            scope_type=scope_type,
            scope_id=scope_id,
            target_root_id=target_root_id,
            target_folder=target_folder,
        )
        plan = self._plan_from_inputs(data, dry_run=dry_run)
        self._storage.save_plan(plan)
        self._audit.append(
            AuditEvent(
                event_type="sync_plan_created",
                entity_type="sync_plan",
                entity_id=plan.id,
                status="success",
                details=json.dumps(
                    {
                        "planner_version": PLANNER_VERSION,
                        "scope_type": plan.scope_type.value,
                        "scope_id": plan.scope_id,
                        "operations": len(plan.operations),
                        "downloadOperations": int(plan.summary.get("readyToDownload", 0)),
                        "uploadOperations": int(plan.summary.get("readyToUpload", 0)),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )[:16000],
            )
        )
        return plan

    def current_fingerprint(
        self,
        *,
        scope_type: str | SyncScopeType,
        scope_id: str | None,
        target_root_id: int | None,
        target_folder: str | None,
    ) -> str:
        data = self._read_inputs(
            scope_type=scope_type,
            scope_id=scope_id,
            target_root_id=target_root_id,
            target_folder=target_folder,
        )
        return self._fingerprint(data)

    def show_plan(self, plan_id: str) -> SyncPlan:
        return self._storage.get_plan(plan_id)

    def cancel_plan(self, plan_id: str) -> None:
        self._storage.cancel_plan(plan_id)
        self._audit.append(
            AuditEvent(
                event_type="sync_plan_cancelled",
                entity_type="sync_plan",
                entity_id=plan_id,
                status="success",
                details="plan status changed to cancelled",
            )
        )

    def _read_inputs(
        self,
        *,
        scope_type: str | SyncScopeType,
        scope_id: str | None,
        target_root_id: int | None,
        target_folder: str | None,
    ) -> _PlanInput:
        scope, clean_scope_id, collection_id = self._resolve_scope(scope_type, scope_id)
        tracks: list[dict[str, Any]] = []
        offset = 0
        while True:
            batch, total = self._coverage.list_tracks(
                provider_id=SOURCE_PROVIDER,
                collection_id=collection_id,
                sort="position" if collection_id else "artist",
                limit=500,
                offset=offset,
            )
            tracks.extend(batch)
            offset += len(batch)
            if not batch or offset >= total:
                break
        external_ids = [str(item.get("externalId") or "") for item in tracks]
        recovery = self._recovery.by_external_ids(external_ids)
        return _PlanInput(
            scope_type=scope,
            scope_id=clean_scope_id,
            collection_id=collection_id,
            target_root_id=target_root_id,
            target_folder=target_folder,
            tracks=tracks,
            recovery=recovery,
            managed=self._recovery_storage.managed_playlists(),
            local_fingerprint=self._matching.local_library_fingerprint(),
            active_downloads=self._active_downloads(),
        )

    def _resolve_scope(
        self, scope_type: str | SyncScopeType, scope_id: str | None
    ) -> tuple[SyncScopeType, str | None, str]:
        try:
            scope = scope_type if isinstance(scope_type, SyncScopeType) else SyncScopeType(str(scope_type))
        except ValueError as exc:
            raise SyncPlannerError("Unsupported sync scope.") from exc
        if scope == SyncScopeType.ALL:
            return scope, None, ""
        collections = {str(item["id"]): item for item in self._coverage.collections(provider_id=SOURCE_PROVIDER)}
        if scope == SyncScopeType.LIKED:
            if "liked" not in collections:
                raise SyncPlannerError("Active Yandex 'Мне нравится' collection is not cached.")
            return scope, "liked", "liked"
        if scope == SyncScopeType.PLAYLIST:
            clean = str(scope_id or "").strip()
            item = collections.get(clean)
            if not clean or item is None or str(item.get("type")) != "playlist":
                raise SyncPlannerError("Selected Yandex playlist is not active in the local cache.")
            return scope, clean, clean
        raise SyncPlannerError("Legacy scope cannot be used to create a current plan.")

    def _active_downloads(self) -> dict[str, str]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT source_id, id FROM download_tasks
                    WHERE task_type='provider_download' AND provider_id=?
                      AND status IN ('queued','running')
                    ORDER BY created_at DESC
                    """,
                    (DOWNLOAD_PROVIDER,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise SyncPlannerError("Failed to inspect current download queue.") from exc
        result: dict[str, str] = {}
        for source_id, task_id in rows:
            result.setdefault(str(source_id), str(task_id))
        return result

    @staticmethod
    def _managed_kind(data: _PlanInput, role: str) -> str | None:
        item = data.managed.get(role)
        value = str(item.get("playlistKind") or "").strip() if item else ""
        return value or None

    def _recovery_operation(
        self,
        data: _PlanInput,
        recovery: RecoveryTrack,
        metadata: dict[str, Any],
    ) -> SyncOperation | None:
        role: str | None = None
        reason: str | None = None
        if recovery.state == RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE:
            role = "unavailable"
            reason = "provider_unavailable_local_mp3"
        elif recovery.state == RecoveryState.CENSORED_ORIGINAL_AVAILABLE:
            role = "censored"
            reason = "confirmed_censored_provider_confirmed_original_local"
        if role is None or reason is None or recovery.local_file_id is None:
            return None
        target_kind = self._managed_kind(data, role)
        if target_kind is None:
            return None
        return SyncOperation(
            operation_type=SyncOperationType.UPLOAD_LOCAL_TO_YANDEX,
            entity_id=recovery.external_id,
            reason=reason,
            confidence=1.0,
            is_dangerous=True,
            metadata={
                **metadata,
                "localFileId": recovery.local_file_id,
                "providerAvailability": recovery.provider_availability.value,
                "providerContentLabel": recovery.provider_content_label,
                "localContentLabel": recovery.local_content_label,
                "recoveryState": recovery.state.value,
                "targetRole": role,
                "targetPlaylistKind": target_kind,
            },
            status=SyncOperationStatus.PENDING,
        )

    def _plan_from_inputs(self, data: _PlanInput, *, dry_run: bool) -> SyncPlan:
        operations: list[SyncOperation] = []
        counts: dict[str, Any] = {
            "desiredTracks": len(data.tracks),
            "alreadyCovered": 0,
            "readyToDownload": 0,
            "alreadyQueued": 0,
            "missingUndecided": 0,
            "ignoredMissing": 0,
            "identityReview": 0,
            "notAnalyzed": 0,
            "variantIssues": 0,
            "localOnly": 0,
            "unavailableTracks": 0,
            "unavailableRecoverable": 0,
            "unavailableMissingLocal": 0,
            "censoredTracks": 0,
            "censoredRecoverable": 0,
            "censoredNeedsReview": 0,
            "readyToUpload": 0,
            "uploadBlocked": 0,
            "uploadByRole": {"censored": 0, "unavailable": 0},
        }

        for track in data.tracks:
            external_id = str(track.get("externalId") or "")
            coverage = str(track.get("coverageStatus") or "not_analyzed")
            action = str(track.get("userAction") or "unreviewed")
            variant = str(track.get("variantStatus") or "not_checked")
            metadata = self._track_snapshot(track)
            recovery = data.recovery.get(external_id)

            if recovery is not None:
                if recovery.state in {
                    RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE,
                    RecoveryState.UNAVAILABLE_LOCAL_MISSING,
                }:
                    counts["unavailableTracks"] += 1
                if recovery.state == RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE:
                    counts["unavailableRecoverable"] += 1
                elif recovery.state == RecoveryState.UNAVAILABLE_LOCAL_MISSING:
                    counts["unavailableMissingLocal"] += 1
                elif recovery.state == RecoveryState.CENSORED_ORIGINAL_AVAILABLE:
                    counts["censoredTracks"] += 1
                    counts["censoredRecoverable"] += 1
                elif recovery.state == RecoveryState.CENSORED_ORIGINAL_MISSING:
                    counts["censoredTracks"] += 1
                elif recovery.state == RecoveryState.CENSORSHIP_NEEDS_REVIEW:
                    counts["censoredNeedsReview"] += 1

                upload_op = self._recovery_operation(data, recovery, metadata)
                if upload_op is not None:
                    operations.append(upload_op)
                    counts["readyToUpload"] += 1
                    role = str(upload_op.metadata.get("targetRole") or "")
                    if role in counts["uploadByRole"]:
                        counts["uploadByRole"][role] += 1
                elif recovery.state in {
                    RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE,
                    RecoveryState.CENSORED_ORIGINAL_AVAILABLE,
                }:
                    counts["uploadBlocked"] += 1

                if recovery.state in {
                    RecoveryState.UNAVAILABLE_LOCAL_MISSING,
                    RecoveryState.UNAVAILABLE_NEEDS_REVIEW,
                    RecoveryState.CENSORSHIP_NEEDS_REVIEW,
                }:
                    operations.append(
                        SyncOperation(
                            operation_type=SyncOperationType.USER_DECISION_REQUIRED,
                            entity_id=external_id,
                            reason=recovery.state.value,
                            metadata={**metadata, "recoveryState": recovery.state.value},
                            status=SyncOperationStatus.INFORMATIONAL,
                        )
                    )
                # A reliably unavailable provider track is never auto-enqueued for
                # download.  That would confuse provider availability with local
                # Coverage and usually cannot restore the source.
                if recovery.provider_availability.value == "unavailable":
                    if coverage == "covered":
                        counts["alreadyCovered"] += 1
                    continue

            if coverage == "covered":
                counts["alreadyCovered"] += 1
                if variant in _VARIANT_REVIEW:
                    counts["variantIssues"] += 1
                    # Variant analysis alone is review-only and never becomes a
                    # censorship upload without explicit content labels.
                    if recovery is None or recovery.state != RecoveryState.CENSORSHIP_NEEDS_REVIEW:
                        operations.append(
                            SyncOperation(
                                operation_type=SyncOperationType.REVIEW_VARIANT,
                                entity_id=external_id,
                                reason=f"variant_{variant}",
                                confidence=float(track.get("confidence") or 0.0),
                                metadata=metadata,
                                status=SyncOperationStatus.INFORMATIONAL,
                            )
                        )
                continue

            if coverage == "missing":
                if action == "wanted":
                    active_task = data.active_downloads.get(external_id)
                    if active_task:
                        counts["alreadyQueued"] += 1
                        operations.append(
                            SyncOperation(
                                operation_type=SyncOperationType.ENQUEUE_DOWNLOAD,
                                entity_id=external_id,
                                reason="already_queued",
                                confidence=1.0,
                                metadata=metadata,
                                status=SyncOperationStatus.SKIPPED,
                                result={"reason": "already_queued", "task_id": active_task},
                            )
                        )
                    else:
                        counts["readyToDownload"] += 1
                        operations.append(
                            SyncOperation(
                                operation_type=SyncOperationType.ENQUEUE_DOWNLOAD,
                                entity_id=external_id,
                                reason="missing_wanted",
                                confidence=1.0,
                                metadata=metadata,
                                status=SyncOperationStatus.PENDING,
                            )
                        )
                elif action == "ignored":
                    counts["ignoredMissing"] += 1
                else:
                    counts["missingUndecided"] += 1
                    operations.append(
                        SyncOperation(
                            operation_type=SyncOperationType.USER_DECISION_REQUIRED,
                            entity_id=external_id,
                            reason="missing_unreviewed",
                            metadata=metadata,
                            status=SyncOperationStatus.INFORMATIONAL,
                        )
                    )
                continue

            if coverage == "needs_review":
                counts["identityReview"] += 1
                operations.append(
                    SyncOperation(
                        operation_type=SyncOperationType.REVIEW_IDENTITY,
                        entity_id=external_id,
                        reason="identity_needs_review",
                        confidence=float(track.get("confidence") or 0.0),
                        metadata=metadata,
                        status=SyncOperationStatus.INFORMATIONAL,
                    )
                )
                continue

            counts["notAnalyzed"] += 1
            operations.append(
                SyncOperation(
                    operation_type=SyncOperationType.REVIEW_IDENTITY,
                    entity_id=external_id,
                    reason="matching_required",
                    metadata={**metadata, "matchingRequired": True},
                    status=SyncOperationStatus.INFORMATIONAL,
                )
            )

        local_only = self._local_only_rows(data)
        counts["localOnly"] = len(local_only)
        outside_reason = "outside_selected_scope" if data.scope_type == SyncScopeType.PLAYLIST else "local_only"
        for row in local_only:
            operations.append(
                SyncOperation(
                    operation_type=SyncOperationType.LOCAL_ONLY,
                    entity_id=str(row[0]),
                    reason=outside_reason,
                    metadata={
                        "localFileId": int(row[0]),
                        "title": str(row[1] or ""),
                        "artists": self._safe_json_list(row[2]),
                        "album": row[3],
                    },
                    status=SyncOperationStatus.INFORMATIONAL,
                )
            )

        desired = counts["desiredTracks"]
        covered = counts["alreadyCovered"]
        projected = covered + counts["readyToDownload"]
        counts["currentCoveragePercent"] = round((covered / desired * 100.0) if desired else 0.0, 1)
        counts["projectedCoveragePercent"] = round((projected / desired * 100.0) if desired else 0.0, 1)
        counts["operationCount"] = len(operations)
        counts["blockerCount"] = (
            counts["missingUndecided"]
            + counts["identityReview"]
            + counts["notAnalyzed"]
            + counts["variantIssues"]
            + counts["uploadBlocked"]
            + counts["censoredNeedsReview"]
        )
        has_download = any(
            op.operation_type == SyncOperationType.ENQUEUE_DOWNLOAD
            and op.status == SyncOperationStatus.PENDING
            for op in operations
        )

        return SyncPlan(
            dry_run=dry_run,
            operations=operations,
            summary=counts,
            planner_version=PLANNER_VERSION,
            scope_type=data.scope_type,
            scope_id=data.scope_id,
            target_root_id=data.target_root_id if has_download else None,
            target_folder=data.target_folder if has_download else None,
            input_fingerprint=self._fingerprint(data),
        )

    def _local_only_rows(self, data: _PlanInput) -> list[tuple[Any, ...]]:
        desired = [str(item.get("externalId") or "") for item in data.tracks if item.get("externalId")]
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                if desired:
                    conn.execute("DROP TABLE IF EXISTS temp.sync_desired_ids")
                    conn.execute("CREATE TEMP TABLE sync_desired_ids(external_id TEXT PRIMARY KEY)")
                    conn.executemany(
                        "INSERT OR IGNORE INTO sync_desired_ids(external_id) VALUES (?)",
                        ((value,) for value in desired),
                    )
                    rows = conn.execute(
                        """
                        SELECT laf.id, laf.title, laf.artists_json, laf.album
                        FROM local_audio_files laf
                        WHERE COALESCE(laf.availability, 'missing')='available'
                          AND NOT EXISTS (
                              SELECT 1 FROM track_links tl
                              JOIN sync_desired_ids d ON d.external_id=tl.source_external_id
                              WHERE tl.local_file_id=laf.id AND tl.source_provider_id=?
                          )
                        ORDER BY COALESCE(laf.title, laf.file_name, laf.path) COLLATE NOCASE, laf.id
                        """,
                        (SOURCE_PROVIDER,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, title, artists_json, album FROM local_audio_files
                        WHERE COALESCE(availability, 'missing')='available'
                        ORDER BY COALESCE(title, file_name, path) COLLATE NOCASE, id
                        """
                    ).fetchall()
        except sqlite3.Error as exc:
            raise SyncPlannerError("Failed to compute local-only sync information.") from exc
        return list(rows)

    def _requires_download_target(self, data: _PlanInput) -> bool:
        for item in data.tracks:
            external_id = str(item.get("externalId") or "")
            recovery = data.recovery.get(external_id)
            if recovery is not None and recovery.provider_availability.value == "unavailable":
                continue
            if str(item.get("coverageStatus") or "") == "missing" and str(item.get("userAction") or "") == "wanted":
                if external_id not in data.active_downloads:
                    return True
        return False

    def _fingerprint(self, data: _PlanInput) -> str:
        tracks: list[dict[str, Any]] = []
        for item in data.tracks:
            external_id = str(item.get("externalId") or "")
            collections = item.get("collections") if isinstance(item.get("collections"), list) else []
            memberships = sorted(
                (
                    str(value.get("id") or ""),
                    int(value.get("position") or 0),
                )
                for value in collections
                if isinstance(value, dict)
                and (data.scope_type == SyncScopeType.ALL or str(value.get("id") or "") == data.collection_id)
            )
            recovery = data.recovery.get(external_id)
            tracks.append(
                {
                    "provider": str(item.get("providerId") or ""),
                    "external": external_id,
                    "membership": memberships,
                    "coverage": str(item.get("coverageStatus") or ""),
                    "matching": str(item.get("matchingStatus") or ""),
                    "local": item.get("localFileId"),
                    "matchingUpdatedAt": item.get("matchingUpdatedAt"),
                    "action": str(item.get("userAction") or "unreviewed"),
                    "variant": str(item.get("variantStatus") or "not_checked"),
                    "recovery": recovery.state.value if recovery else None,
                    "providerAvailability": recovery.provider_availability.value if recovery else None,
                    "providerContentLabel": recovery.provider_content_label if recovery else None,
                    "localContentLabel": recovery.local_content_label if recovery else None,
                }
            )
        requires_download = self._requires_download_target(data)
        payload = {
            "plannerVersion": PLANNER_VERSION,
            "scopeType": data.scope_type.value,
            "scopeId": data.scope_id,
            "targetRootId": data.target_root_id if requires_download else None,
            "targetFolder": data.target_folder if requires_download else None,
            "localLibraryFingerprint": data.local_fingerprint,
            "managedPlaylists": {
                role: str(item.get("playlistKind") or "") for role, item in sorted(data.managed.items())
            },
            "tracks": sorted(tracks, key=lambda value: (value["provider"], value["external"])),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _track_snapshot(track: dict[str, Any]) -> dict[str, Any]:
        provider = track.get("provider") if isinstance(track.get("provider"), dict) else {}
        raw_artists = provider.get("artists") or []
        artists = [str(value) for value in raw_artists] if isinstance(raw_artists, list) else [str(raw_artists)]
        return {
            "providerId": str(track.get("providerId") or ""),
            "externalId": str(track.get("externalId") or ""),
            "title": str(provider.get("title") or track.get("externalId") or ""),
            "artists": artists,
            "album": provider.get("album_title") or provider.get("album"),
            "coverageStatus": str(track.get("coverageStatus") or ""),
            "userAction": str(track.get("userAction") or "unreviewed"),
            "variantStatus": track.get("variantStatus"),
        }

    @staticmethod
    def _safe_json_list(value: object) -> list[str]:
        try:
            decoded = json.loads(str(value or "[]"))
        except (TypeError, json.JSONDecodeError):
            return []
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
