"""Provider-neutral Compare/Apply facade over the existing explicit Metadata Editor."""

from __future__ import annotations

from typing import Any

from musicark.metadata.models import BASIC_FIELDS, nonempty
from musicark.metadata.service import MetadataEditorService

from .resolver import ExternalMetadataResolver


class ExternalMetadataEditor:
    def __init__(self, service: MetadataEditorService, resolver: ExternalMetadataResolver) -> None:
        self._service = service
        self._resolver = resolver

    def compare(self, local_file_id: int, candidate_id: str) -> dict[str, Any]:
        local = self._service.get(local_file_id)["metadata"]
        candidate = self._resolver.candidate(local_file_id, candidate_id)
        external_fields = dict(candidate.get("fields") or {})
        local_fields = dict(local.get("fields") or {})
        rows: list[dict[str, Any]] = []
        for field in BASIC_FIELDS:
            if field == "artwork":
                local_value = bool((local.get("artwork") or {}).get("present"))
                external_value = bool((candidate.get("artwork") or {}).get("cachePath"))
            else:
                local_value = local_fields.get(field)
                external_value = external_fields.get(field)
            rows.append({
                "field": field,
                "local": local_value,
                "external": external_value,
                "available": bool(nonempty(external_value)),
                "selected": bool(nonempty(external_value)),
                "source": (candidate.get("provenance") or {}).get(field, candidate.get("source")),
            })
        return {"local": local, "external": candidate, "rows": rows}

    def apply(self, local_file_id: int, candidate_id: str, selected_fields: list[str], *, confirm: bool) -> dict[str, Any]:
        if confirm is not True:
            raise ValueError("External metadata import requires explicit confirmation.")
        candidate = self._resolver.candidate(local_file_id, candidate_id)
        fields = dict(candidate.get("fields") or {})
        selected = set(selected_fields)
        patch: dict[str, Any] = {}
        for field in selected:
            if field == "artwork":
                continue
            value = fields.get(field)
            if nonempty(value):
                patch[field] = value
        artwork_path = str((candidate.get("artwork") or {}).get("cachePath") or "").strip()
        if "artwork" in selected and artwork_path:
            patch["artworkImagePath"] = artwork_path
        if not patch:
            raise ValueError("No available external metadata fields were selected.")

        result = self._service.update(local_file_id, patch, confirm=True)
        # Persist only provider-neutral identities after the user explicitly applies
        # a candidate. This table is evidence/provenance; it does not overwrite the
        # trusted Yandex source_provider_id/source_external_id columns.
        self._resolver.persist_candidate_identities(local_file_id, candidate_id)
        result["external"] = {
            "candidateId": candidate_id,
            "source": candidate.get("source"),
            "appliedFields": sorted(field for field in selected if field in fields or (field == "artwork" and artwork_path)),
            "identityBound": False,
            "externalIdentitiesPersisted": True,
        }
        return result
