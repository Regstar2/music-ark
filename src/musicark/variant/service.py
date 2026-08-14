"""Application orchestration for v0.5.1 variant / altered-track detection."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from musicark.core.config import load_config
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from .audio import AudioDecodeError, AudioDecoderUnavailable, AudioVerifier
from .classifier import VariantClassifier
from .metadata import MetadataVariantDetector
from .models import VariantResult, VariantStatus
from .policy import ANALYZER_VERSION, SAMPLE_RATE
from .reference import ReferenceAudioResolver, file_fingerprint
from .storage import VariantStorageRepository


_TECHNICAL_REASONS = {
    "audio_decoder_unavailable",
    "decode_error",
    "local_file_missing",
    "reference_file_missing",
    "alignment_failed",
    "audio_too_short",
    "insufficient_aligned_overlap",
    "no_comparison_windows",
    "permission_error",
}


class VariantDetectionService:
    """Verify recording variants only after v0.5 established track identity."""

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        database_path: Path | None = None,
        provider_id: str = "yandex_music",
        audio_verifier: AudioVerifier | None = None,
        reference_resolver: ReferenceAudioResolver | None = None,
    ) -> None:
        self._base_dir = base_dir
        self._provider_id = provider_id
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._storage = VariantStorageRepository(self._database_path)
        self._metadata = MetadataVariantDetector()
        self._audio = audio_verifier or AudioVerifier()
        self._resolver = reference_resolver or ReferenceAudioResolver(
            self._database_path,
            base_dir,
        )
        self._classifier = VariantClassifier()
        self._audit = AuditLogRepository(self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def capabilities(self) -> dict[str, Any]:
        return {
            "providerId": self._provider_id,
            "ffmpegAvailable": self._audio.available,
            "audioVerificationAvailable": self._audio.available,
            "sampleRate": SAMPLE_RATE,
            "analyzerVersion": ANALYZER_VERSION,
            "unavailableMessage": (
                None
                if self._audio.available
                else "Аудиосравнение недоступно: ffmpeg не найден"
            ),
        }

    def summary(self) -> dict[str, Any]:
        summary = self._storage.summary(self._provider_id)
        summary["capabilities"] = self.capabilities()
        return summary

    def results(
        self,
        *,
        limit: int = 500,
        offset: int = 0,
        status: str = "",
    ) -> dict[str, Any]:
        return self._storage.list_results(
            self._provider_id,
            limit=limit,
            offset=offset,
            status=status,
        )

    def result(self, external_id: str) -> dict[str, Any]:
        pair = self._required_pair(external_id)
        local_id = int(pair["local"]["id"])
        saved = self._storage.get(self._provider_id, external_id, local_id)
        if saved is None:
            saved = self._not_checked_payload(pair, external_id)
        return {
            "result": saved,
            "identity": {
                "status": pair["identityStatus"],
                "confidence": pair["identityConfidence"],
                "method": pair["identityMethod"],
            },
        }

    def run(self, external_id: str, *, force: bool = False) -> dict[str, Any]:
        pair = self._required_pair(external_id)
        provider = self._normalized_provider(dict(pair["provider"]))
        local = dict(pair["local"])
        local_id = int(local["id"])
        local_path = Path(str(local.get("path") or ""))
        metadata = self._metadata.analyze(provider, local)
        provider_fp = self._provider_variant_fingerprint(provider, metadata.as_dict())
        local_fp = self._local_fingerprint(local, local_path)
        reference = self._resolver.resolve(self._provider_id, external_id)
        reference_fp = ""
        if reference is not None and reference.path.is_file():
            try:
                reference_fp = file_fingerprint(reference.path)
            except OSError:
                reference = None

        existing = self._storage.get(self._provider_id, external_id, local_id)
        if (
            not force
            and existing is not None
            and int(existing.get("analyzerVersion") or 0) == ANALYZER_VERSION
            and existing.get("providerVariantFingerprint") == provider_fp
            and existing.get("localAudioFingerprint") == local_fp
            and existing.get("referenceAudioFingerprint") == reference_fp
            and self._cacheable(existing)
        ):
            return {"result": existing, "cached": True, "capabilities": self.capabilities()}

        provider_duration = self._number(provider.get("duration_seconds"))
        local_duration = self._number(local.get("duration_seconds"))

        if not local_path.is_file():
            result = self._technical_result(
                external_id,
                local_id,
                VariantStatus.UNCERTAIN,
                metadata,
                ("local_file_missing",),
                provider_fp,
                local_fp,
                reference_fp,
                reference.path if reference else None,
            )
            return self._save(result, cached=False)

        if reference is None:
            status, reasons = self._classifier.classify(
                metadata,
                None,
                provider_duration=provider_duration,
                local_duration=local_duration,
                reference_available=False,
                audio_available=self._audio.available,
            )
            result = self._result_from(
                external_id,
                local_id,
                status,
                reasons,
                metadata,
                provider_fp,
                local_fp,
                "",
                None,
                None,
            )
            return self._save(result, cached=False)

        if not self._audio.available:
            status, reasons = self._classifier.classify(
                metadata,
                None,
                provider_duration=provider_duration,
                local_duration=local_duration,
                reference_available=True,
                audio_available=False,
            )
            result = self._result_from(
                external_id,
                local_id,
                status,
                reasons,
                metadata,
                provider_fp,
                local_fp,
                reference_fp,
                reference.path,
                None,
            )
            return self._save(result, cached=False)

        try:
            comparison = self._audio.compare(reference.path, local_path)
        except AudioDecoderUnavailable:
            result = self._technical_result(
                external_id,
                local_id,
                VariantStatus.NOT_CHECKED,
                metadata,
                ("audio_decoder_unavailable",),
                provider_fp,
                local_fp,
                reference_fp,
                reference.path,
            )
            return self._save(result, cached=False)
        except PermissionError:
            result = self._technical_result(
                external_id,
                local_id,
                VariantStatus.UNCERTAIN,
                metadata,
                ("permission_error",),
                provider_fp,
                local_fp,
                reference_fp,
                reference.path,
            )
            return self._save(result, cached=False)
        except (AudioDecodeError, OSError, ValueError) as exc:
            reason = self._technical_reason(exc)
            result = self._technical_result(
                external_id,
                local_id,
                VariantStatus.UNCERTAIN,
                metadata,
                (reason,),
                provider_fp,
                local_fp,
                reference_fp,
                reference.path,
            )
            return self._save(result, cached=False)

        status, reasons = self._classifier.classify(
            metadata,
            comparison,
            provider_duration=provider_duration,
            local_duration=local_duration,
            reference_available=True,
            audio_available=True,
        )
        audio_metadata = metadata.as_dict()
        audio_metadata.update(
            {
                "alignmentOffsetSeconds": round(comparison.alignment_offset_seconds, 4),
                "alignmentConfidence": round(comparison.alignment_confidence, 6),
                "medianWindowSimilarity": round(comparison.median_window_similarity, 6),
                "lowSimilarityWindowRatio": round(comparison.low_similarity_window_ratio, 6),
                "windowCount": comparison.window_count,
            }
        )
        result = VariantResult(
            provider_id=self._provider_id,
            external_id=external_id,
            local_file_id=local_id,
            status=status,
            reasons=reasons,
            audio_similarity=round(comparison.global_similarity, 6),
            metadata_score=round(metadata.metadata_score, 6),
            altered_regions=comparison.altered_regions,
            provider_variant_fingerprint=provider_fp,
            local_audio_fingerprint=local_fp,
            reference_audio_fingerprint=reference_fp,
            analyzer_version=ANALYZER_VERSION,
            reference_path=str(reference.path),
            metadata=audio_metadata,
        )
        return self._save(result, cached=False)

    def run_all_available(self) -> dict[str, Any]:
        pairs = self._storage.list_matched_pairs(self._provider_id)
        available_ids = [
            str(pair["externalId"])
            for pair in pairs
            if self._resolver.resolve(self._provider_id, str(pair["externalId"])) is not None
        ]
        counts = {item.value: 0 for item in VariantStatus}
        cached = 0
        errors = 0
        for external_id in available_ids:
            try:
                payload = self.run(external_id)
                result = payload.get("result") if isinstance(payload, dict) else None
                if isinstance(result, dict):
                    status = str(result.get("variantStatus") or result.get("status") or "")
                    if status in counts:
                        counts[status] += 1
                if payload.get("cached"):
                    cached += 1
            except Exception:  # noqa: BLE001 - one bad file must not abort the batch.
                errors += 1
        summary = {
            "eligibleMatched": len(pairs),
            "available": len(available_ids),
            "processed": len(available_ids),
            "cached": cached,
            "errors": errors,
            "same": counts[VariantStatus.SAME.value],
            "altered": counts[VariantStatus.ALTERED.value],
            "differentVersion": counts[VariantStatus.DIFFERENT_VERSION.value],
            "uncertain": counts[VariantStatus.UNCERTAIN.value],
            "notChecked": counts[VariantStatus.NOT_CHECKED.value],
            "progress": {"completed": len(available_ids), "total": len(available_ids)},
        }
        self._audit.append(
            AuditEvent(
                event_type="variant_run_all",
                entity_type="variant_detection_service",
                entity_id=self._provider_id,
                status="success" if errors == 0 else "partial",
                details=json.dumps(summary, ensure_ascii=False, sort_keys=True),
            )
        )
        return summary

    def _required_pair(self, external_id: str) -> dict[str, Any]:
        clean = str(external_id).strip()
        if not clean:
            raise ValueError("external_id is required")
        pair = self._storage.matched_pair(self._provider_id, clean)
        if pair is None:
            raise ValueError(
                f"Variant analysis requires a MATCHED identity for {self._provider_id}:{clean}."
            )
        return pair

    @staticmethod
    def _normalized_provider(provider: dict[str, Any]) -> dict[str, Any]:
        value = dict(provider)
        if value.get("duration_seconds") is None and value.get("durationSeconds") is not None:
            value["duration_seconds"] = value.get("durationSeconds")
        if value.get("album_title") is None and value.get("album") is not None:
            value["album_title"] = value.get("album")
        if value.get("explicit") is None and value.get("content_warning") is not None:
            value["explicit"] = bool(value.get("content_warning"))
        return value

    @staticmethod
    def _provider_variant_fingerprint(provider: dict[str, Any], evidence: dict[str, Any]) -> str:
        relevant = {
            "title": provider.get("title"),
            "artists": provider.get("artists"),
            "album": provider.get("album_title", provider.get("album")),
            "duration": provider.get("duration_seconds"),
            "explicit": provider.get("explicit"),
            "markers": evidence.get("providerMarkers", []),
        }
        raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _local_fingerprint(local: dict[str, Any], path: Path) -> str:
        try:
            stat = path.stat()
            size = stat.st_size
            modified_ns = stat.st_mtime_ns
        except OSError:
            size = int(local.get("file_size") or 0)
            modified_ns = int(local.get("modified_ns") or 0)
        relevant = {
            "path": str(path),
            "fileSize": int(size),
            "modifiedNs": int(modified_ns),
        }
        raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cacheable(existing: dict[str, Any]) -> bool:
        reasons = {str(item) for item in existing.get("variantReasons", [])}
        return not bool(reasons & _TECHNICAL_REASONS)

    @staticmethod
    def _technical_reason(exc: Exception) -> str:
        text = str(exc).strip().casefold()
        known = (
            "alignment_failed",
            "audio_too_short",
            "insufficient_aligned_overlap",
            "no_comparison_windows",
        )
        for value in known:
            if value in text:
                return value
        return "decode_error"

    def _technical_result(
        self,
        external_id: str,
        local_id: int,
        status: VariantStatus,
        metadata: Any,
        technical_reasons: tuple[str, ...],
        provider_fp: str,
        local_fp: str,
        reference_fp: str,
        reference_path: Path | None,
    ) -> VariantResult:
        reasons = tuple(dict.fromkeys([*metadata.reasons, *technical_reasons]))
        return self._result_from(
            external_id,
            local_id,
            status,
            reasons,
            metadata,
            provider_fp,
            local_fp,
            reference_fp,
            reference_path,
            None,
        )

    def _result_from(
        self,
        external_id: str,
        local_id: int,
        status: VariantStatus,
        reasons: tuple[str, ...],
        metadata: Any,
        provider_fp: str,
        local_fp: str,
        reference_fp: str,
        reference_path: Path | None,
        audio_similarity: float | None,
    ) -> VariantResult:
        return VariantResult(
            provider_id=self._provider_id,
            external_id=external_id,
            local_file_id=local_id,
            status=status,
            reasons=tuple(dict.fromkeys(reasons)),
            audio_similarity=audio_similarity,
            metadata_score=round(float(metadata.metadata_score), 6),
            altered_regions=(),
            provider_variant_fingerprint=provider_fp,
            local_audio_fingerprint=local_fp,
            reference_audio_fingerprint=reference_fp,
            analyzer_version=ANALYZER_VERSION,
            reference_path=str(reference_path) if reference_path is not None else None,
            metadata=metadata.as_dict(),
        )

    def _save(self, result: VariantResult, *, cached: bool) -> dict[str, Any]:
        saved = self._storage.upsert(result)
        self._audit.append(
            AuditEvent(
                event_type="variant_run",
                entity_type="provider_track",
                entity_id=f"{result.provider_id}:{result.external_id}",
                status=result.status.value,
                details=(
                    f"local_file_id={result.local_file_id} "
                    f"audio_similarity={result.audio_similarity} reasons={','.join(result.reasons)}"
                ),
            )
        )
        return {"result": saved, "cached": cached, "capabilities": self.capabilities()}

    @staticmethod
    def _not_checked_payload(pair: dict[str, Any], external_id: str) -> dict[str, Any]:
        return {
            "providerId": pair["providerId"],
            "externalId": external_id,
            "localFileId": int(pair["local"]["id"]),
            "status": VariantStatus.NOT_CHECKED.value,
            "variantStatus": VariantStatus.NOT_CHECKED.value,
            "metadataScore": None,
            "metadata": {},
            "audioSimilarity": None,
            "variantReasons": ["audio_not_checked"],
            "alteredSegments": [],
            "referencePath": None,
            "analyzerVersion": ANALYZER_VERSION,
        }
