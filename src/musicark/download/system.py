"""Download queue orchestration for v0.5."""

from __future__ import annotations

from datetime import UTC, datetime

from musicark.core.errors import MusicArkError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.download_storage import DownloadStorageRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository
from musicark.providers.models import TrackSource

from .models import DownloadStatus, DownloadTask
from .provider import DownloadProvider, DownloadProviderError


class DownloadSystemError(MusicArkError):
    """Raised for queue/registry problems in download-system."""


class DownloadProviderRegistry:
    """Registry for download providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DownloadProvider] = {}

    def register(self, provider: DownloadProvider) -> None:
        if provider.provider_id in self._providers:
            raise DownloadSystemError(f"Download provider '{provider.provider_id}' already exists.")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> DownloadProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise DownloadSystemError(f"Download provider '{provider_id}' is not registered.") from exc


class DownloadSystem:
    """Minimal universal queue for file acquisition."""

    def __init__(self, database_path) -> None:  # type: ignore[no-untyped-def]
        self._database_path = database_path
        self._download_storage = DownloadStorageRepository(database_path)
        self._local_storage = LocalLibraryStorageRepository(database_path)
        self._audit = AuditLogRepository(database_path)
        self._registry = DownloadProviderRegistry()

    def register_provider(self, provider: DownloadProvider) -> None:
        self._registry.register(provider)

    def create_task(
        self, task_type: str, source_id: str, provider_id: str, target_folder: str
    ) -> DownloadTask:
        task = DownloadTask(
            task_type=task_type,
            source_id=source_id,
            provider_id=provider_id,
            target_folder=target_folder,
            status=DownloadStatus.QUEUED,
        )
        self._download_storage.upsert_task(task)
        self._audit.append(
            AuditEvent(
                event_type="download_task_created",
                entity_type="download_task",
                entity_id=task.id,
                status="success",
                details=f"provider={provider_id} source={source_id}",
            )
        )
        return task

    def queue(self) -> list[DownloadTask]:
        return self._download_storage.list_tasks()

    def run_task(self, task_id: str) -> DownloadTask:
        task = self._download_storage.get_task(task_id)
        provider = self._registry.get(task.provider_id)
        if task.status in {DownloadStatus.CANCELLED, DownloadStatus.COMPLETED}:
            raise DownloadSystemError(f"Task '{task_id}' cannot be executed from status {task.status}.")

        task.status = DownloadStatus.RUNNING
        task.started_at = datetime.now(UTC).isoformat()
        task.progress = 0.1
        self._download_storage.upsert_task(task)

        try:
            local_audio_file = provider.execute(task)
            local_id = self._local_storage.upsert_local_audio_file_and_return_id(local_audio_file)
            source = TrackSource(
                track_id=f"local:{local_audio_file.sha256}",
                source_type="local_file",
                provider_id="local_library",
                external_id=local_audio_file.path,
                url=local_audio_file.path,
                availability="available",
                raw_data={"origin_task_id": task.id},
            )
            self._local_storage.upsert_track_source(source)

            task.status = DownloadStatus.COMPLETED
            task.progress = 1.0
            task.error_message = None
            task.result_local_file_id = local_id
            task.finished_at = datetime.now(UTC).isoformat()
            self._download_storage.upsert_task(task)
            self._audit.append(
                AuditEvent(
                    event_type="download_task_completed",
                    entity_type="download_task",
                    entity_id=task.id,
                    status="success",
                    details=f"provider={task.provider_id} result_local_file_id={local_id}",
                )
            )
            return task
        except DownloadProviderError as exc:
            task.status = DownloadStatus.FAILED
            task.progress = 0.0
            task.error_message = str(exc)
            task.finished_at = datetime.now(UTC).isoformat()
            self._download_storage.upsert_task(task)
            self._audit.append(
                AuditEvent(
                    event_type="download_task_failed",
                    entity_type="download_task",
                    entity_id=task.id,
                    status="failed",
                    details=str(exc),
                )
            )
            return task

    def cancel_task(self, task_id: str) -> DownloadTask:
        task = self._download_storage.get_task(task_id)
        if task.status in {DownloadStatus.COMPLETED, DownloadStatus.CANCELLED}:
            return task
        task.status = DownloadStatus.CANCELLED
        task.finished_at = datetime.now(UTC).isoformat()
        self._download_storage.upsert_task(task)
        return task

    def retry_task(self, task_id: str) -> DownloadTask:
        task = self._download_storage.get_task(task_id)
        if task.status not in {DownloadStatus.FAILED, DownloadStatus.NEEDS_REVIEW}:
            raise DownloadSystemError("Only failed/needs_review tasks can be retried.")
        task.status = DownloadStatus.QUEUED
        task.progress = 0.0
        task.error_message = None
        task.started_at = None
        task.finished_at = None
        self._download_storage.upsert_task(task)
        return task
