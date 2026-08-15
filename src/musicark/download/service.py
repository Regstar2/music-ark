"""Application-level Download workflow for MusicArk v0.7.

This service owns eligibility, persisted queue state, provider execution, Local
Library indexing, and exact provider/local identity linking. Flutter only sends
commands and reads queue state; it never coordinates these modules itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import time
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError
from musicark.credentials import CredentialStore, CredentialStoreError, SystemCredentialStore
from musicark.coverage.repository import CoverageRepository
from musicark.local_library.service import LocalLibraryService
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.models import MatchDecision, MatchMethod, MatchStatus
from musicark.providers.yandex_music_provider import (
    YandexAuthenticationError,
    YandexMusicError,
    YandexTokenMissingError,
)
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository, normalize_local_path
from musicark.storage.matching_storage import MatchingStorageRepository

from .models import DownloadStatus, DownloadTask
from .provider import (
    DownloadCancelledError,
    DownloadProvider,
    DownloadProviderError,
    YandexMusicDownloadProvider,
    yandex_download_filename,
)
from .system import DownloadProviderRegistry, DownloadSystemError


class DownloadServiceError(MusicArkError):
    def __init__(self, message: str, *, code: str = "download_error") -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _artists(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("artists") or []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _duration(payload: dict[str, Any]) -> float | None:
    raw = payload.get("duration_seconds")
    if raw is None and payload.get("duration_ms") is not None:
        try:
            return float(payload["duration_ms"]) / 1000.0
        except (TypeError, ValueError):
            return None
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


class DownloadService:
    """Coordinate the v0.7 Missing -> Download -> Covered product loop."""

    SOURCE_PROVIDER = "yandex_music"
    DOWNLOAD_PROVIDER = "yandex_music_download"
    MANAGED_FOLDER = "MusicArk"

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        database_path: Path | None = None,
        credential_store: CredentialStore | None = None,
        registry: DownloadProviderRegistry | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._downloads = DownloadStorageRepository(self._database_path)
        self._coverage = CoverageRepository(self._database_path)
        self._local_repo = LocalLibraryStorageRepository(self._database_path)
        self._local = LocalLibraryService(
            base_dir=base_dir,
            repository=self._local_repo,
            database_path=self._database_path,
        )
        self._matching = MatchingStorageRepository(self._database_path)
        self._audit = AuditLogRepository(self._database_path)
        self._credentials = credential_store or SystemCredentialStore()
        self._registry = registry or DownloadProviderRegistry()

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    # ---- Destination ---------------------------------------------------------
    def settings(self) -> dict[str, Any]:
        root_id = self._downloads.get_target_root_id()
        root = next((item for item in self._local_repo.list_roots() if item.id == root_id), None)
        if root is None:
            return {"targetConfigured": False, "rootId": None, "rootPath": None, "targetPath": None}
        target = Path(root.path) / self.MANAGED_FOLDER
        return {
            "targetConfigured": True,
            "rootId": root.id,
            "rootPath": root.path,
            "targetPath": str(target),
        }

    def set_target(self, path: str) -> dict[str, Any]:
        selected = Path(path).expanduser().resolve(strict=False)
        if not selected.exists() or not selected.is_dir():
            raise DownloadServiceError("Selected download folder is not accessible.", code="target_invalid")
        normalized = normalize_local_path(selected)
        roots = self._local_repo.list_roots()
        root = next((item for item in roots if item.normalized_path == normalized), None)
        if root is None:
            for item in roots:
                existing = Path(item.path).expanduser().resolve(strict=False)
                try:
                    selected.relative_to(existing)
                except ValueError:
                    continue
                root = item
                break
        if root is None:
            try:
                root = self._local_repo.add_root(selected)
            except ValueError as exc:
                raise DownloadServiceError(str(exc), code="target_overlap") from exc
        self._downloads.set_target_root_id(root.id)
        self._audit_event("download_target_changed", "success", f"root_id={root.id}")
        return self.settings()

    def _target(self) -> tuple[int, Path]:
        settings = self.settings()
        if not settings["targetConfigured"]:
            raise DownloadServiceError("Выберите папку для загрузок.", code="target_required")
        root_id = int(settings["rootId"])
        target = Path(str(settings["targetPath"])).resolve(strict=False)
        root_path = Path(str(settings["rootPath"])).resolve(strict=False)
        try:
            target.relative_to(root_path)
        except ValueError as exc:
            raise DownloadServiceError("Download target escapes Local Library root.", code="unsafe_path") from exc
        return root_id, target

    # ---- Queue ---------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        return {"counts": self._downloads.summary(), "settings": self.settings()}

    def tasks(self, *, status: str = "", limit: int = 1000) -> dict[str, Any]:
        tasks = self._downloads.list_tasks(status=status, limit=limit)
        return {"count": len(tasks), "items": [self._task_payload(task) for task in tasks]}

    def enqueue(self, external_id: str, *, provider_id: str = SOURCE_PROVIDER) -> dict[str, Any]:
        identity = str(external_id).strip()
        if not identity:
            raise DownloadServiceError("Track external id is required.", code="invalid_request")
        track = self._coverage.get_track(provider_id=provider_id, external_id=identity)
        if track is None:
            raise DownloadServiceError("Provider track is not present in the cached library.", code="track_missing")
        task, created = self._enqueue_track(track)
        return {"created": created, "task": self._task_payload(task)}

    def enqueue_wanted(self, *, provider_id: str = SOURCE_PROVIDER) -> dict[str, Any]:
        offset = 0
        created = 0
        existing = 0
        items: list[dict[str, Any]] = []
        while True:
            batch, total = self._coverage.list_tracks(
                provider_id=provider_id,
                status="missing",
                user_action="wanted",
                limit=500,
                offset=offset,
            )
            for track in batch:
                task, was_created = self._enqueue_track(track)
                created += 1 if was_created else 0
                existing += 0 if was_created else 1
                if len(items) < 100:
                    items.append(self._task_payload(task))
            offset += len(batch)
            if not batch or offset >= total:
                break
        return {"created": created, "existing": existing, "items": items}

    def _enqueue_track(self, track: dict[str, Any]) -> tuple[DownloadTask, bool]:
        if track.get("coverageStatus") != "missing" or track.get("userAction") != "wanted":
            raise DownloadServiceError(
                "Only tracks with coverage=missing and action=wanted can be downloaded.",
                code="not_eligible",
            )
        source_provider = str(track.get("providerId") or self.SOURCE_PROVIDER)
        if source_provider != self.SOURCE_PROVIDER:
            raise DownloadServiceError("No download provider is configured for this source.", code="provider_unsupported")
        external_id = str(track["externalId"])
        active = self._downloads.find_active(self.DOWNLOAD_PROVIDER, external_id)
        if active is not None:
            return active, False

        root_id, target = self._target()
        payload = dict(track.get("provider") or {})
        title = str(payload.get("title") or external_id)
        artists = _artists(payload)
        safe_payload = {
            "source_provider_id": source_provider,
            "track_id": external_id,
            "quality": "best",
            "title": title,
            "artists": artists,
            "duration_seconds": _duration(payload),
            "target_filename": yandex_download_filename(artists, title, external_id),
        }

        retryable = self._downloads.find_retryable(self.DOWNLOAD_PROVIDER, external_id)
        if retryable is not None:
            retryable.status = DownloadStatus.QUEUED
            retryable.progress = 0.0
            retryable.downloaded_bytes = 0
            retryable.total_bytes = None
            retryable.cancel_requested = False
            retryable.target_root_id = root_id
            retryable.target_folder = str(target)
            retryable.raw_payload = safe_payload
            retryable.started_at = None
            retryable.finished_at = None
            retryable.error_code = None
            retryable.error_message = None
            retryable.result_local_file_id = None
            self._downloads.upsert_task(retryable)
            self._audit_event("download_enqueued", "success", f"provider={source_provider} source={external_id}", retryable.id)
            return retryable, True

        task = DownloadTask(
            task_type="provider_download",
            source_id=external_id,
            provider_id=self.DOWNLOAD_PROVIDER,
            target_folder=str(target),
            target_root_id=root_id,
            status=DownloadStatus.QUEUED,
            raw_payload=safe_payload,
        )
        self._downloads.upsert_task(task)
        self._audit_event("download_enqueued", "success", f"provider={source_provider} source={external_id}", task.id)
        return task, True

    def retry(self, task_id: str) -> dict[str, Any]:
        task = self._downloads.get_task(task_id)
        if task.status not in {DownloadStatus.FAILED, DownloadStatus.NEEDS_REVIEW}:
            raise DownloadServiceError("Only failed or needs-review downloads can be retried.", code="not_retryable")
        review_retry = task.status == DownloadStatus.NEEDS_REVIEW
        track = self._coverage.get_track(provider_id=self.SOURCE_PROVIDER, external_id=task.source_id)
        coverage_status = track.get("coverageStatus") if track else None
        user_action = track.get("userAction") if track else None
        if (
            track is None
            or coverage_status == "covered"
            or user_action != "wanted"
            or (not review_retry and coverage_status != "missing")
            or (review_retry and coverage_status not in {"missing", "not_analyzed", "needs_review"})
        ):
            task.status = DownloadStatus.SKIPPED
            task.error_code = "already_covered" if coverage_status == "covered" else "not_eligible"
            task.error_message = "Track is no longer eligible for this retry."
            task.finished_at = _now()
            self._downloads.upsert_task(task)
            return {"task": self._task_payload(task)}
        task.status = DownloadStatus.QUEUED
        task.progress = 0.0
        task.downloaded_bytes = 0
        task.total_bytes = None
        task.cancel_requested = False
        task.started_at = None
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        task.raw_payload["review_retry"] = review_retry
        self._downloads.upsert_task(task)
        return {"task": self._task_payload(task)}

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self._downloads.request_cancel(task_id)
        self._audit_event("download_cancel_requested", "success", f"status={task.status.value}", task.id)
        return {"task": self._task_payload(task)}

    def clear_completed(self) -> dict[str, Any]:
        return {"removed": self._downloads.clear_completed()}

    def recover_interrupted(self) -> dict[str, Any]:
        return {"recovered": self._downloads.recover_interrupted()}

    # ---- Execution -----------------------------------------------------------
    def run(self, *, limit: int | None = None) -> dict[str, Any]:
        """Run queued tasks sequentially (bounded concurrency = 1)."""
        if self._downloads.summary().get("running", 0):
            raise DownloadServiceError("A download worker is already running.", code="worker_busy")
        queued = sorted(
            self._downloads.list_tasks(status="queued", limit=5000),
            key=lambda item: item.created_at,
        )
        if limit is not None:
            queued = queued[: max(0, int(limit))]
        results = [self.run_task(task.id) for task in queued]
        return {"processed": len(results), "items": [self._task_payload(item) for item in results]}

    def run_task(self, task_id: str) -> DownloadTask:
        task = self._downloads.get_task(task_id)
        if task.status != DownloadStatus.QUEUED:
            raise DownloadServiceError(
                f"Task cannot run from status {task.status.value}.", code="invalid_state"
            )
        current = self._coverage.get_track(provider_id=self.SOURCE_PROVIDER, external_id=task.source_id)
        ordinary_eligible = bool(
            current
            and current.get("coverageStatus") == "missing"
            and current.get("userAction") == "wanted"
        )
        review_retry = bool(task.raw_payload.get("review_retry"))
        review_retry_eligible = bool(
            review_retry
            and current
            and current.get("coverageStatus") in {"missing", "not_analyzed", "needs_review"}
            and current.get("userAction") == "wanted"
        )
        if not ordinary_eligible and not review_retry_eligible:
            task.status = DownloadStatus.SKIPPED
            task.error_code = "not_missing"
            task.error_message = "Track is no longer an eligible Missing + Wanted item."
            task.finished_at = _now()
            self._downloads.upsert_task(task)
            self._audit_event("download_skipped", "success", task.error_message, task.id)
            return task

        task.status = DownloadStatus.RUNNING
        task.started_at = _now()
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        task.cancel_requested = False
        self._downloads.upsert_task(task)
        self._audit_event("download_started", "success", f"source={task.source_id}", task.id)

        target_filename = str(task.raw_payload.get("target_filename") or f"yandex_{task.source_id}.mp3")
        target_folder = Path(task.target_folder).resolve(strict=False)
        expected_path = (target_folder / target_filename).resolve(strict=False)
        existed_before = expected_path.exists()
        cleanup_new_final = not existed_before
        last_write = 0.0
        last_bytes = 0
        last_cancel_check = 0.0
        cancel_cache = False

        def persist_progress(downloaded: int, total: int | None) -> None:
            nonlocal last_write, last_bytes
            now = time.monotonic()
            if (
                now - last_write >= 0.35
                or downloaded - last_bytes >= 1024 * 1024
                or (total is not None and downloaded >= total)
            ):
                self._downloads.update_progress(task.id, downloaded, total)
                last_write = now
                last_bytes = downloaded

        def cancelled() -> bool:
            nonlocal last_cancel_check, cancel_cache
            now = time.monotonic()
            if now - last_cancel_check >= 0.2:
                cancel_cache = self._downloads.is_cancel_requested(task.id)
                last_cancel_check = now
            return cancel_cache

        try:
            provider = self._provider(task.provider_id)
            local_audio = provider.execute_with_context(
                task,
                progress=persist_progress,
                cancelled=cancelled,
            )
            actual_path = Path(local_audio.path).resolve(strict=False)
            if actual_path.parent != target_folder:
                raise DownloadServiceError(
                    "Download provider returned a file outside the selected target.",
                    code="unsafe_path",
                )
            cleanup_new_final = not (existed_before and actual_path == expected_path)
            if actual_path.name != target_filename:
                task.raw_payload["target_filename"] = actual_path.name
                self._downloads.upsert_task(task)

            indexed = self._local.index_file(actual_path, int(task.target_root_id or 0))["track"]
            self._validate_duration(current.get("provider") or {}, indexed)
            local_id = int(indexed["id"])
            provider_payload = dict(current.get("provider") or {})
            decision = MatchDecision(
                provider_id=self.SOURCE_PROVIDER,
                external_id=task.source_id,
                provider_payload=provider_payload,
                provider_fingerprint=provider_fingerprint(
                    self.SOURCE_PROVIDER, task.source_id, provider_payload
                ),
                # Automatic v0.5 decisions store the whole Local Library fingerprint.
                # Compute it only after the new file has been indexed.
                local_fingerprint=self._matching.local_library_fingerprint(),
                status=MatchStatus.MATCHED,
                local_file_id=local_id,
                confidence=1.0,
                method=MatchMethod.EXACT_ID,
                breakdown={"exact_id": 1.0, "final": 1.0},
                reason="download_exact",
            )
            self._matching.persist_batch([decision])
            refreshed = self._coverage.get_track(
                provider_id=self.SOURCE_PROVIDER, external_id=task.source_id
            )
            if refreshed is None or refreshed.get("coverageStatus") != "covered":
                raise DownloadServiceError(
                    "Downloaded track was indexed but Coverage did not become covered.",
                    code="coverage_not_updated",
                )

            size = actual_path.stat().st_size
            task = self._downloads.get_task(task.id)
            task.status = DownloadStatus.COMPLETED
            task.progress = 1.0
            task.downloaded_bytes = int(size)
            task.total_bytes = task.total_bytes or int(size)
            task.error_code = None
            task.error_message = None
            task.result_local_file_id = local_id
            task.finished_at = _now()
            task.cancel_requested = False
            task.raw_payload.pop("review_retry", None)
            self._downloads.upsert_task(task)
            self._audit_event(
                "download_completed",
                "success",
                f"source={task.source_id} local_file_id={local_id}",
                task.id,
            )
            return task
        except DownloadCancelledError as exc:
            return self._fail_or_cancel(task, exc, status=DownloadStatus.CANCELLED)
        except (YandexTokenMissingError, YandexAuthenticationError, CredentialStoreError) as exc:
            return self._fail_or_cancel(task, exc, code="authentication")
        except DownloadProviderError as exc:
            return self._fail_or_cancel(task, exc, code=exc.code)
        except DownloadServiceError as exc:
            review = exc.code in {"duration_mismatch", "coverage_not_updated"}
            return self._fail_or_cancel(
                task,
                exc,
                code=exc.code,
                status=DownloadStatus.NEEDS_REVIEW if review else DownloadStatus.FAILED,
                cleanup=cleanup_new_final and not review,
            )
        except YandexMusicError as exc:
            return self._fail_or_cancel(task, exc, code="provider_request")
        except (OSError, ValueError) as exc:
            return self._fail_or_cancel(task, exc, code="invalid_audio", cleanup=cleanup_new_final)
        except Exception as exc:  # noqa: BLE001 - queue must remain recoverable.
            return self._fail_or_cancel(task, exc, code="unexpected")

    def _provider(self, provider_id: str) -> DownloadProvider:
        try:
            return self._registry.get(provider_id)
        except DownloadSystemError:
            if provider_id != self.DOWNLOAD_PROVIDER:
                raise DownloadServiceError(
                    f"Download provider '{provider_id}' is not registered.", code="provider_unsupported"
                )
            token = self._credentials.get_token()
            if not token:
                raise YandexTokenMissingError("Saved Yandex Music token is missing.")
            provider = YandexMusicDownloadProvider(base_dir=self._base_dir, token=token)
            self._registry.register(provider)
            return provider

    @staticmethod
    def _validate_duration(provider_payload: dict[str, Any], indexed: dict[str, Any]) -> None:
        expected = _duration(provider_payload)
        actual_raw = indexed.get("durationSeconds")
        try:
            actual = float(actual_raw) if actual_raw is not None else None
        except (TypeError, ValueError):
            actual = None
        if expected is None or actual is None or expected <= 0 or actual <= 0:
            return
        difference = abs(expected - actual)
        if difference > max(15.0, expected * 0.10):
            raise DownloadServiceError(
                f"Downloaded audio duration differs from provider metadata by {difference:.1f}s.",
                code="duration_mismatch",
            )

    def _fail_or_cancel(
        self,
        task: DownloadTask,
        exc: Exception,
        *,
        code: str | None = None,
        status: DownloadStatus = DownloadStatus.FAILED,
        cleanup: bool = False,
    ) -> DownloadTask:
        current = self._downloads.get_task(task.id)
        final_status = status
        if isinstance(exc, DownloadCancelledError) or current.cancel_requested:
            final_status = DownloadStatus.CANCELLED
            code = "cancelled"
        if cleanup:
            target_filename = str(current.raw_payload.get("target_filename") or "")
            if target_filename:
                try:
                    target_folder = Path(current.target_folder).resolve(strict=False)
                    candidate = (target_folder / target_filename).resolve(strict=False)
                    if candidate.parent == target_folder:
                        candidate.unlink(missing_ok=True)
                except OSError:
                    pass
        current.status = final_status
        current.error_code = code or "download_error"
        current.error_message = self._public_error(exc, current.error_code)
        current.finished_at = _now()
        current.cancel_requested = False
        current.progress = 0.0 if final_status != DownloadStatus.COMPLETED else current.progress
        self._downloads.upsert_task(current)
        if final_status == DownloadStatus.CANCELLED:
            event = "download_cancelled"
        elif final_status == DownloadStatus.NEEDS_REVIEW:
            event = "download_needs_review"
        else:
            event = "download_failed"
        self._audit_event(event, "failed", f"code={current.error_code} source={current.source_id}", current.id)
        return current

    @staticmethod
    def _public_error(exc: Exception, code: str) -> str:
        if code == "authentication":
            return "Требуется повторная авторизация Яндекс Музыки."
        if code == "track_unavailable":
            return "Трек недоступен для загрузки через Яндекс Музыку."
        if code == "no_download_info":
            return "Яндекс Музыка не предоставила данные для загрузки этого трека."
        if code == "cancelled":
            return "Загрузка отменена."
        text = str(exc).strip()
        return text or "Download failed."

    def _audit_event(self, event_type: str, status: str, details: str, task_id: str | None = None) -> None:
        self._audit.append(
            AuditEvent(
                event_type=event_type,
                entity_type="download_task" if task_id else "download_settings",
                entity_id=task_id,
                status=status,
                details=details,
            )
        )

    @staticmethod
    def _task_payload(task: DownloadTask) -> dict[str, Any]:
        artists = task.raw_payload.get("artists") or []
        return {
            "id": task.id,
            "provider": str(task.raw_payload.get("source_provider_id") or task.provider_id),
            "downloadProvider": task.provider_id,
            "externalId": task.source_id,
            "title": str(task.raw_payload.get("title") or task.source_id),
            "artists": artists if isinstance(artists, list) else [],
            "status": task.status.value,
            "progress": task.progress if task.total_bytes else None,
            "downloadedBytes": task.downloaded_bytes,
            "totalBytes": task.total_bytes,
            "targetPath": str(Path(task.target_folder) / str(task.raw_payload.get("target_filename") or "")),
            "errorCode": task.error_code,
            "error": task.error_message,
            "createdAt": task.created_at,
            "updatedAt": task.updated_at,
            "startedAt": task.started_at,
            "finishedAt": task.finished_at,
            "localFileId": task.result_local_file_id,
            "canRetry": task.status in {DownloadStatus.FAILED, DownloadStatus.NEEDS_REVIEW},
            "canCancel": task.status in {DownloadStatus.QUEUED, DownloadStatus.RUNNING},
        }
