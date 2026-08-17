"""User decisions for reviewed recording variants.

The analyzer result remains authoritative. Acceptance is a separate decision saying
that the currently analyzed local recording is good enough for the user.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database

from .storage import VariantStorageRepository


_REVIEWABLE = {"altered", "different_version", "uncertain"}


class VariantAcceptanceError(MusicArkError):
    """Invalid explicit variant-acceptance operation."""


class VariantAcceptanceService:
    """Persist a user decision without rewriting the analyzer classification."""

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
        self._variants = VariantStorageRepository(self._database_path)
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def _variant(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        result = self._variants.get(
            self._provider_id,
            str(external_id),
            int(local_file_id),
        )
        if result is None:
            raise VariantAcceptanceError(
                "Сначала необходимо выполнить проверку версии этого сопоставления."
            )
        return result

    @staticmethod
    def _evidence(result: dict[str, Any]) -> tuple[str, str, str, int, str | None]:
        return (
            str(result.get("providerVariantFingerprint") or ""),
            str(result.get("localAudioFingerprint") or ""),
            str(result.get("referenceAudioFingerprint") or ""),
            int(result.get("analyzerVersion") or 0),
            result.get("updatedAt"),
        )

    def get(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        result = self._variant(external_id, local_file_id)
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                """
                SELECT variant_status, provider_variant_fingerprint,
                       local_audio_fingerprint, reference_audio_fingerprint,
                       analyzer_version, analysis_updated_at, accepted_at
                FROM variant_user_acceptance
                WHERE provider_id=? AND external_id=? AND local_file_id=?
                """,
                (self._provider_id, str(external_id), int(local_file_id)),
            ).fetchone()
        current_evidence = self._evidence(result)
        accepted = bool(
            row
            and str(row[0]) == str(result.get("variantStatus") or result.get("status") or "")
            and str(row[1] or "") == current_evidence[0]
            and str(row[2] or "") == current_evidence[1]
            and str(row[3] or "") == current_evidence[2]
            and int(row[4] or 0) == current_evidence[3]
            and (row[5] or None) == current_evidence[4]
        )
        return {
            "providerId": self._provider_id,
            "externalId": str(external_id),
            "localFileId": int(local_file_id),
            "variantStatus": str(result.get("variantStatus") or result.get("status") or "not_checked"),
            "accepted": accepted,
            "acceptedAt": row[6] if accepted and row else None,
        }

    def accept(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        result = self._variant(external_id, local_file_id)
        status = str(result.get("variantStatus") or result.get("status") or "not_checked")
        if status not in _REVIEWABLE:
            raise VariantAcceptanceError(
                "Принятие требуется только для изменённой, другой или неопределённой версии."
            )
        provider_fp, local_fp, reference_fp, analyzer_version, updated_at = self._evidence(result)
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO variant_user_acceptance(
                        provider_id, external_id, local_file_id, variant_status,
                        provider_variant_fingerprint, local_audio_fingerprint,
                        reference_audio_fingerprint, analyzer_version,
                        analysis_updated_at, accepted_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))
                    ON CONFLICT(provider_id, external_id, local_file_id) DO UPDATE SET
                        variant_status=excluded.variant_status,
                        provider_variant_fingerprint=excluded.provider_variant_fingerprint,
                        local_audio_fingerprint=excluded.local_audio_fingerprint,
                        reference_audio_fingerprint=excluded.reference_audio_fingerprint,
                        analyzer_version=excluded.analyzer_version,
                        analysis_updated_at=excluded.analysis_updated_at,
                        accepted_at=datetime('now')
                    """,
                    (
                        self._provider_id,
                        str(external_id),
                        int(local_file_id),
                        status,
                        provider_fp,
                        local_fp,
                        reference_fp,
                        analyzer_version,
                        updated_at,
                    ),
                )
        self._audit.append(
            AuditEvent(
                event_type="variant_user_acceptance",
                entity_type="provider_track",
                entity_id=f"{self._provider_id}:{external_id}",
                status="success",
                details=f"local_file_id={int(local_file_id)} variant_status={status} accepted=true",
            )
        )
        return self.get(external_id, local_file_id)

    def reset(self, external_id: str, local_file_id: int) -> dict[str, Any]:
        self._variant(external_id, local_file_id)
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    DELETE FROM variant_user_acceptance
                    WHERE provider_id=? AND external_id=? AND local_file_id=?
                    """,
                    (self._provider_id, str(external_id), int(local_file_id)),
                )
        self._audit.append(
            AuditEvent(
                event_type="variant_user_acceptance",
                entity_type="provider_track",
                entity_id=f"{self._provider_id}:{external_id}",
                status="success",
                details=f"local_file_id={int(local_file_id)} accepted=false",
            )
        )
        return self.get(external_id, local_file_id)
