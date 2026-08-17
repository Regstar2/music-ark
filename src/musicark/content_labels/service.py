"""Persist user-assigned content-version labels without mutating audio metadata."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database


VALID_CONTENT_LABELS = frozenset({"original", "censored"})


class ContentLabelError(MusicArkError):
    """Raised when a content-version label request is invalid."""


class ContentLabelService:
    """Store app-level ORIGINAL/CENSORED marks for local and provider identities."""

    def __init__(self, base_dir: Path | None = None, *, database_path: Path | None = None) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    @staticmethod
    def _label(value: str | None) -> str | None:
        clean = str(value or "").strip().casefold()
        if not clean:
            return None
        if clean not in VALID_CONTENT_LABELS:
            raise ContentLabelError("Content label must be 'original', 'censored', or empty.")
        return clean

    def batch(
        self,
        *,
        local_file_ids: list[int] | tuple[int, ...] = (),
        provider_id: str = "yandex_music",
        external_ids: list[str] | tuple[str, ...] = (),
    ) -> dict[str, Any]:
        local_ids = list(dict.fromkeys(int(item) for item in local_file_ids))[:5000]
        provider = str(provider_id).strip() or "yandex_music"
        provider_ids = list(dict.fromkeys(str(item).strip() for item in external_ids if str(item).strip()))[:5000]
        local: dict[str, str] = {}
        remote: dict[str, str] = {}
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                if local_ids:
                    for offset in range(0, len(local_ids), 500):
                        batch = local_ids[offset : offset + 500]
                        marks = ",".join("?" for _ in batch)
                        rows = conn.execute(
                            f"SELECT local_file_id, label FROM local_track_content_labels WHERE local_file_id IN ({marks})",
                            batch,
                        ).fetchall()
                        local.update({str(row[0]): str(row[1]) for row in rows})
                if provider_ids:
                    for offset in range(0, len(provider_ids), 500):
                        batch = provider_ids[offset : offset + 500]
                        marks = ",".join("?" for _ in batch)
                        rows = conn.execute(
                            f"""
                            SELECT external_id, label FROM provider_track_content_labels
                            WHERE provider_id=? AND external_id IN ({marks})
                            """,
                            [provider, *batch],
                        ).fetchall()
                        remote.update({str(row[0]): str(row[1]) for row in rows})
        except sqlite3.Error as exc:
            raise ContentLabelError("Failed to load content-version labels.") from exc
        return {"local": local, "provider": remote, "providerId": provider}

    def set_local(self, local_file_id: int, label: str | None) -> dict[str, Any]:
        file_id = int(local_file_id)
        clean = self._label(label)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM local_audio_files WHERE id=? AND availability='available'",
                    (file_id,),
                ).fetchone()
                if exists is None:
                    raise ContentLabelError(f"Local file {file_id} is not available.")
                with conn:
                    if clean is None:
                        conn.execute(
                            "DELETE FROM local_track_content_labels WHERE local_file_id=?",
                            (file_id,),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO local_track_content_labels(local_file_id, label)
                            VALUES (?, ?)
                            ON CONFLICT(local_file_id) DO UPDATE SET
                                label=excluded.label, updated_at=datetime('now')
                            """,
                            (file_id, clean),
                        )
        except ContentLabelError:
            raise
        except sqlite3.Error as exc:
            raise ContentLabelError("Failed to save the local content-version label.") from exc
        self._audit.append(
            AuditEvent(
                event_type="content_label_set",
                entity_type="local_audio_file",
                entity_id=str(file_id),
                status="success",
                details=f"label={clean or 'unset'}",
            )
        )
        return {"subject": "local", "localFileId": file_id, "label": clean}

    def set_provider(
        self,
        external_id: str,
        label: str | None,
        *,
        provider_id: str = "yandex_music",
    ) -> dict[str, Any]:
        provider = str(provider_id).strip() or "yandex_music"
        identity = str(external_id).strip()
        if not identity:
            raise ContentLabelError("Provider external id is required.")
        clean = self._label(label)
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                with conn:
                    if clean is None:
                        conn.execute(
                            """
                            DELETE FROM provider_track_content_labels
                            WHERE provider_id=? AND external_id=?
                            """,
                            (provider, identity),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO provider_track_content_labels(provider_id, external_id, label)
                            VALUES (?, ?, ?)
                            ON CONFLICT(provider_id, external_id) DO UPDATE SET
                                label=excluded.label, updated_at=datetime('now')
                            """,
                            (provider, identity, clean),
                        )
        except sqlite3.Error as exc:
            raise ContentLabelError("Failed to save the provider content-version label.") from exc
        self._audit.append(
            AuditEvent(
                event_type="content_label_set",
                entity_type="provider_track",
                entity_id=f"{provider}:{identity}",
                status="success",
                details=f"label={clean or 'unset'}",
            )
        )
        return {
            "subject": "provider",
            "providerId": provider,
            "externalId": identity,
            "label": clean,
        }
