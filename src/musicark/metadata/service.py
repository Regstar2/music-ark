"""Coordinates metadata edits with [[storage]] and [[history-audit-log]]."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from musicark.core.errors import MetadataEditorError, StorageError
from musicark.metadata.engine import (
    StructuredTags,
    apply_structured_patch,
    backup_audio_file,
    read_structured,
    validate_text,
    validate_track_number,
    validate_year,
)
from musicark.providers.local_library import build_local_audio_file
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.local_library_storage import LocalLibraryStorageRepository


class MetadataEditorService:
    """Read/write structured tags on indexed local_audio_files."""

    def __init__(self, database_path: Path, base_dir: Path | None) -> None:
        self._database_path = database_path
        self._base_dir = base_dir.resolve() if base_dir is not None else database_path.resolve().parent
        self._storage = LocalLibraryStorageRepository(database_path)
        self._audit = AuditLogRepository(database_path)

    def _backup_dir(self) -> Path:
        return self._base_dir / ".musicark" / "metadata_backups"

    def fetch_structured_tags(self, local_file_id: int) -> dict[str, Any]:
        row = self._storage.fetch_local_audio_file_row_by_id(local_file_id)
        if row is None:
            raise MetadataEditorError(f"No local_audio_file id={local_file_id}.")
        path = Path(row["path"])
        if not path.is_file():
            raise MetadataEditorError(f"Indexed file missing on disk: {path}")
        structured = read_structured(path).as_dict()
        return {
            "local_file_id": local_file_id,
            "path": str(path.resolve()),
            "codec": row.get("codec", ""),
            "tags": structured,
        }

    def _resolve_path_row(self, file_id: int) -> tuple[Path, dict[str, Any]]:
        row = self._storage.fetch_local_audio_file_row_by_id(file_id)
        if row is None:
            raise MetadataEditorError(f"No local_audio_file id={file_id}.")
        path = Path(row["path"])
        if not path.is_file():
            raise MetadataEditorError(f"Indexed file missing on disk: {path}")
        return path.resolve(), row

    def _normalized_write_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if "title" in payload:
            out["title"] = validate_text("title", payload["title"])
        if "artist" in payload:
            out["artist"] = validate_text("artist", payload["artist"])
        if "album" in payload:
            out["album"] = validate_text("album", payload["album"])
        if "genre" in payload:
            out["genre"] = validate_text("genre", payload["genre"])
        if "track_number" in payload:
            out["track_number"] = validate_track_number(payload["track_number"])
        if "year" in payload:
            out["year"] = validate_year(payload["year"])
        if payload.get("clear_cover"):
            out["clear_cover"] = True
        cp = payload.get("cover_image_path")
        if cp:
            out["cover_image_path"] = str(cp)
        return out

    def _apply_disk_and_db(self, path: Path, fields: dict[str, Any]) -> tuple[str, StructuredTags, StructuredTags]:
        dest = backup_audio_file(path, self._backup_dir())
        backup_path_str = str(dest.resolve())
        before, after = apply_structured_patch(
            path,
            title=fields.get("title"),
            artist=fields.get("artist"),
            album=fields.get("album"),
            track_number=fields.get("track_number"),
            year=fields.get("year"),
            genre=fields.get("genre"),
            clear_cover=bool(fields.get("clear_cover")),
            cover_image_path=fields.get("cover_image_path"),
        )
        updated = build_local_audio_file(path)
        self._storage.upsert_local_audio_file(updated)
        return backup_path_str, before, after

    def update_tags(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("confirm") is not True:
            raise MetadataEditorError(
                'Metadata writes require explicit JSON flag "confirm": true in the bridge payload.'
            )
        fid = payload.get("local_file_id")
        try:
            file_id = int(fid)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise MetadataEditorError("Payload must contain integer local_file_id.") from exc

        path, _row = self._resolve_path_row(file_id)
        fields = self._normalized_write_fields(payload)
        if not fields:
            raise MetadataEditorError(
                "No fields to update — include at least title, artist, album, genre, "
                "track_number, year, clear_cover and/or cover_image_path."
            )

        backup_path_str = ""
        try:
            backup_path_str, before_raw, after_raw = self._apply_disk_and_db(path, fields)
        except MetadataEditorError as exc:
            self._audit.append(
                AuditEvent(
                    event_type="metadata_update",
                    entity_type="local_audio_file",
                    entity_id=str(file_id),
                    status="failed",
                    details=json.dumps(
                        {"path": str(path), "error": str(exc)},
                        ensure_ascii=False,
                    )[:16000],
                )
            )
            raise
        except Exception as exc:  # noqa: BLE001 — unexpected filesystem/mutagen
            self._audit.append(
                AuditEvent(
                    event_type="metadata_update",
                    entity_type="local_audio_file",
                    entity_id=str(file_id),
                    status="failed",
                    details=json.dumps({"path": str(path), "error": str(exc)}, ensure_ascii=False)[:16000],
                )
            )
            raise MetadataEditorError(f"Metadata write failed: {exc}") from exc

        try:
            self._audit.append(
                AuditEvent(
                    event_type="metadata_update",
                    entity_type="local_audio_file",
                    entity_id=str(file_id),
                    status="success",
                    details=json.dumps(
                        {
                            "path": str(path),
                            "backup_path": backup_path_str,
                            "before": before_raw.as_dict(),
                            "after": after_raw.as_dict(),
                        },
                        ensure_ascii=False,
                    )[:20000],
                )
            )
        except Exception:  # noqa: BLE001
            pass

        return {
            "local_file_id": file_id,
            "path": str(path),
            "backup_path": backup_path_str,
            "tags": after_raw.as_dict(),
        }

    def bulk_update_tags(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("confirm") is not True:
            raise MetadataEditorError('Bulk writes require {\"confirm\": true}.')
        raw_ids = payload.get("local_file_ids")
        if not isinstance(raw_ids, list) or len(raw_ids) < 2:
            raise MetadataEditorError('"local_file_ids" must list at least two ids for bulk update.')
        ids: list[int] = []
        for x in raw_ids:
            try:
                ids.append(int(x))
            except (TypeError, ValueError) as exc:
                raise MetadataEditorError("local_file_ids must contain integers.") from exc

        template = self._normalized_write_fields(payload)
        if not template:
            raise MetadataEditorError("Bulk payload has no metadata fields to apply.")

        succeeded: list[int] = []
        failed: list[dict[str, Any]] = []
        for lf_id in ids:
            path, _row = self._resolve_path_row(lf_id)
            backup_path_str = ""
            try:
                self._apply_disk_and_db(path, template)
                succeeded.append(lf_id)
            except (MetadataEditorError, OSError, StorageError, ValueError, TypeError) as exc:
                failed.append({"local_file_id": lf_id, "error": str(exc)})

        self._audit.append(
            AuditEvent(
                event_type="metadata_bulk_update",
                entity_type="local_audio_file",
                entity_id=",".join(str(i) for i in ids),
                status="success" if not failed else ("partial" if succeeded else "failed"),
                details=json.dumps(
                    {
                        "template": {k: v for k, v in template.items() if k != "cover_image_path"},
                        "succeeded": succeeded,
                        "failed": failed,
                    },
                    ensure_ascii=False,
                )[:20000],
            )
        )
        return {"succeeded": succeeded, "failed": failed}
