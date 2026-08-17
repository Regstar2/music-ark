"""Explicit, transactional Local Metadata Editor orchestration."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid
from typing import Any

from musicark.core.config import load_config
from musicark.core.errors import MusicArkError
from musicark.coverage.service import LibraryCoverageService
from musicark.download.metadata import YandexTrackMetadata
from musicark.local_library.service import LocalLibraryService
from musicark.matching.scoring import MatchScorer
from musicark.provenance import (
    MUSICARK_EXTERNAL_ID,
    MUSICARK_METADATA_SCHEMA,
    MUSICARK_METADATA_SCHEMA_VERSION,
    MUSICARK_PROVIDER,
    YANDEX_ALBUM_ID,
    YANDEX_ARTIST_IDS,
    YANDEX_REAL_ID,
    YANDEX_TRACK_ID,
)
from musicark.storage.audit_log import AuditEvent, AuditLogRepository
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository

from .artwork import ArtworkCache
from .formats.base import MetadataFormatError
from .formats.mp3 import Mp3MetadataAdapter
from .identity import ExplicitIdentityService
from .matching_refresh import TargetedMatchingRefresh
from .models import BASIC_FIELDS, ArtworkInfo, MetadataDocument, nonempty
from .yandex import YandexMetadataGateway, identity_fields, metadata_fields


class MetadataEditorError(MusicArkError):
    """Public explicit-editor error."""


class MetadataEditorService:
    """Only this service may mutate existing user audio, and only on explicit commands."""

    def __init__(self, base_dir: Path | None = None, *, database_path: Path | None = None) -> None:
        self._base_dir = base_dir
        self._database_path = database_path or self._resolve_database_path()
        initialize_database(self._database_path)
        self._audit = AuditLogRepository(self._database_path)
        self._adapter = Mp3MetadataAdapter()
        self._artwork = ArtworkCache(self._database_path, base_dir)
        self._yandex = YandexMetadataGateway(base_dir, self._database_path)
        self._identity = ExplicitIdentityService(self._database_path)
        self._matching = MatchingStorageRepository(self._database_path)
        self._refresh = TargetedMatchingRefresh(self._database_path)
        self._local = LocalLibraryService(base_dir=base_dir, database_path=self._database_path)

    def _resolve_database_path(self) -> Path:
        config = load_config(self._base_dir)
        raw = Path(config.database_path)
        if raw.is_absolute():
            return raw
        root = self._base_dir if self._base_dir is not None else Path.home()
        return root / raw

    def _row(self, local_file_id: int) -> dict[str, Any]:
        try:
            with closing(sqlite3.connect(self._database_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, library_root_id, path, file_name, extension, sha256,
                           file_size, modified_ns, duration_seconds, codec, title,
                           artists_json, album, album_artist, track_number, disc_number,
                           year, genre, bitrate, sample_rate, source_provider_id,
                           source_external_id, availability
                    FROM local_audio_files WHERE id=?
                    """,
                    (int(local_file_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MetadataEditorError("Failed to read the Local Library record.") from exc
        if row is None or row["availability"] != "available":
            raise MetadataEditorError(f"Local file {local_file_id} is not available.")
        result = dict(row)
        try:
            result["artists"] = json.loads(result.get("artists_json") or "[]")
        except json.JSONDecodeError:
            result["artists"] = []
        return result

    def _identity_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        provider_id = row.get("source_provider_id")
        external_id = row.get("source_external_id")
        exact = None
        if provider_id and external_id:
            try:
                with closing(sqlite3.connect(self._database_path)) as conn:
                    exact = conn.execute(
                        """
                        SELECT method, confidence, reason FROM matching_results
                        WHERE provider_id=? AND external_id=? AND local_file_id=?
                        """,
                        (provider_id, external_id, int(row["id"])),
                    ).fetchone()
            except sqlite3.Error:
                exact = None
        if exact is None:
            return {"providerId": provider_id, "externalId": external_id, "status": "not_set" if not external_id else "embedded"}
        return {
            "providerId": provider_id,
            "externalId": external_id,
            "status": "exact" if str(exact[0]) == "exact_id" else str(exact[0]),
            "method": str(exact[0]),
            "confidence": float(exact[1] or 0),
            "reason": exact[2],
        }

    def get(self, local_file_id: int) -> dict[str, Any]:
        row = self._row(local_file_id)
        path = Path(str(row["path"]))
        if not path.is_file():
            raise MetadataEditorError(f"Indexed file is missing on disk: {path}")
        writable = self._adapter.supports(path)
        all_tags: tuple[dict[str, Any], ...] = ()
        if writable:
            parsed = self._adapter.read(path)
            fields = dict(parsed["fields"])
            all_tags = tuple(parsed["allTags"])
        else:
            fields = {
                "title": row.get("title"),
                "artists": row.get("artists") or [],
                "album": row.get("album"),
                "albumArtists": [row["album_artist"]] if row.get("album_artist") else [],
                "trackNumber": row.get("track_number"),
                "discNumber": row.get("disc_number"),
                "year": row.get("year"),
                "genres": [row["genre"]] if row.get("genre") else [],
            }
        art = self._artwork.ensure_local(
            int(row["id"]), path,
            source_external_id=str(row["source_external_id"]) if row.get("source_external_id") else None,
        )
        document = MetadataDocument(
            local_file_id=int(row["id"]), path=str(path), format=str(row.get("codec") or path.suffix.lstrip(".")),
            writable=writable, fields=fields, all_tags=all_tags, artwork=art,
            identity=self._identity_payload(row),
        ).as_dict()
        document["technical"] = {
            "durationSeconds": row.get("duration_seconds"),
            "bitrate": row.get("bitrate"),
            "sampleRate": row.get("sample_rate"),
            "fileSize": row.get("file_size"),
            "sha256": row.get("sha256"),
        }
        return {"metadata": document}

    def artwork_batch(self, local_file_ids: list[int]) -> dict[str, Any]:
        ids = list(dict.fromkeys(int(item) for item in local_file_ids))[:500]
        if not ids:
            return {"items": {}}
        placeholders = ",".join("?" for _ in ids)
        with closing(sqlite3.connect(self._database_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, path, source_external_id FROM local_audio_files
                WHERE availability='available' AND id IN ({placeholders})
                """,
                ids,
            ).fetchall()
        return {"items": self._artwork.batch([dict(row) for row in rows])}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _artwork_file(path_value: Any) -> tuple[bytes | None, str | None]:
        if not path_value:
            return None, None
        path = Path(str(path_value)).expanduser().resolve(strict=False)
        if not path.is_file():
            raise MetadataEditorError(f"Artwork file was not found: {path}")
        data = path.read_bytes()
        if not data or len(data) > 8 * 1024 * 1024:
            raise MetadataEditorError("Artwork must be a non-empty image smaller than 8 MiB.")
        if data.startswith(b"\x89PNG"):
            return data, "image/png"
        if data.startswith(b"\xff\xd8"):
            return data, "image/jpeg"
        raise MetadataEditorError("Only PNG and JPEG artwork is supported for MP3.")

    def _reindex(self, row: dict[str, Any], path: Path) -> dict[str, Any]:
        root_id = row.get("library_root_id")
        if root_id is None:
            raise MetadataEditorError("The edited file is not attached to a Local Library root.")
        payload = self._local.index_file(path, int(root_id))
        digest = self._sha256(path)
        stat = path.stat()
        modified_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    UPDATE local_audio_files SET sha256=?, file_size=?, modified_ns=?, updated_at=datetime('now')
                    WHERE id=?
                    """,
                    (digest, int(stat.st_size), modified_ns, int(row["id"])),
                )
        return payload

    def update(
        self,
        local_file_id: int,
        changes: dict[str, Any],
        *,
        confirm: bool,
        provenance: dict[str, str | None] | None = None,
        artwork_data: bytes | None = None,
        artwork_mime: str | None = None,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise MetadataEditorError("Metadata writes require explicit confirmation.")
        row = self._row(local_file_id)
        path = Path(str(row["path"])).resolve(strict=False)
        if not self._adapter.supports(path):
            raise MetadataEditorError(
                f"Editing '{path.suffix}' is not implemented yet. MP3 is the full v8.2.0 write adapter."
            )
        if not path.is_file():
            raise MetadataEditorError(f"Indexed file is missing on disk: {path}")

        local_artwork_data, local_artwork_mime = self._artwork_file(changes.pop("artworkImagePath", None))
        if local_artwork_data is not None:
            artwork_data, artwork_mime = local_artwork_data, local_artwork_mime
        remove_artwork = bool(changes.pop("removeArtwork", False))
        previous_fingerprint = self._matching.local_library_fingerprint()
        original_duration = self._adapter.validate_audio(path)
        temp = path.with_name(f".{path.stem}.musicark-edit-{uuid.uuid4().hex}{path.suffix}")
        replaced = False
        try:
            shutil.copy2(path, temp)
            self._adapter.apply(
                temp, changes,
                artwork_data=artwork_data,
                artwork_mime=artwork_mime,
                remove_artwork=remove_artwork,
                provenance=provenance,
            )
            temp_duration = self._adapter.validate_audio(temp)
            if original_duration is not None and temp_duration is not None and abs(original_duration - temp_duration) > 0.1:
                raise MetadataEditorError("Audio validation failed: duration changed during metadata edit.")
            # Read-back validation happens before replacement; malformed written tags
            # therefore cannot damage the original file.
            self._adapter.read(temp)
            os.replace(temp, path)
            replaced = True
        except Exception as exc:  # noqa: BLE001
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            self._audit.append(
                AuditEvent(
                    event_type="local_metadata_update", entity_type="local_audio_file",
                    entity_id=str(local_file_id), status="failed",
                    details=json.dumps({"path": str(path), "replaced": replaced, "error": str(exc)}, ensure_ascii=False)[:16000],
                )
            )
            if isinstance(exc, (MetadataEditorError, MetadataFormatError)):
                raise MetadataEditorError(str(exc)) from exc
            raise MetadataEditorError(f"Metadata transaction failed: {exc}") from exc

        # The filesystem transaction is complete. Everything below updates derived
        # MusicArk state for this same file; it never walks or hashes the whole library.
        try:
            indexed = self._reindex(row, path)
            refreshed_artwork = self._artwork.ensure_local(
                int(local_file_id), path,
                source_external_id=(str(row["source_external_id"]) if row.get("source_external_id") else None),
            )
            matching = self._refresh.run(int(local_file_id), previous_fingerprint=previous_fingerprint)
            after = self.get(int(local_file_id))["metadata"]
            self._audit.append(
                AuditEvent(
                    event_type="local_metadata_update", entity_type="local_audio_file",
                    entity_id=str(local_file_id), status="success",
                    details=json.dumps(
                        {
                            "path": str(path), "changedFields": sorted(changes.keys()),
                            "artworkChanged": bool(artwork_data is not None or remove_artwork),
                            "provenanceWritten": provenance is not None,
                            "singleFileReindex": True,
                        },
                        ensure_ascii=False,
                    )[:16000],
                )
            )
            return {
                "metadata": after,
                "index": indexed,
                "matching": matching,
                "artwork": refreshed_artwork.as_dict(),
            }
        except Exception as exc:  # noqa: BLE001
            self._audit.append(
                AuditEvent(
                    event_type="local_metadata_post_write_refresh", entity_type="local_audio_file",
                    entity_id=str(local_file_id), status="failed",
                    details=json.dumps({"path": str(path), "error": str(exc)}, ensure_ascii=False)[:16000],
                )
            )
            raise MetadataEditorError(
                "Metadata was written safely, but derived MusicArk state could not be refreshed: " + str(exc)
            ) from exc

    @staticmethod
    def _provider_payload(metadata: YandexTrackMetadata) -> dict[str, Any]:
        return {
            "provider_id": "yandex_music",
            "external_id": metadata.external_id,
            "title": metadata.title,
            "artists": list(metadata.artists),
            "album_external_id": metadata.album_id,
            "album_title": metadata.album_title,
            "duration_seconds": metadata.duration_seconds,
            "explicit": metadata.explicit,
            "availability": metadata.availability,
            "version": metadata.version,
            "subtitle": metadata.subtitle,
            "real_id": metadata.real_id,
            "artist_ids": list(metadata.artist_ids),
            "album_artists": list(metadata.album_artists),
            "release_year": metadata.release_year,
            "release_date": metadata.release_date,
            "genre": metadata.genre,
            "track_number": metadata.track_number,
            "total_tracks": metadata.total_tracks,
            "disc_number": metadata.disc_number,
            "total_discs": metadata.total_discs,
            "isrc": metadata.isrc,
            "publisher": metadata.publisher,
            "copyright": metadata.copyright,
        }

    def _query_hint(self, document: dict[str, Any]) -> str:
        fields = document.get("fields") or {}
        title = str(fields.get("title") or "").strip()
        artists = [str(item).strip() for item in (fields.get("artists") or []) if str(item).strip()]
        garbage = {"unknown artist", "unknown", "drivemusic.me", "—", "-"}
        useful = [item for item in artists if item.casefold() not in garbage]
        if title and useful:
            return f"{useful[0]} {title}"
        if title:
            return title
        return Path(str(document.get("path") or "")).stem

    def yandex_search(self, local_file_id: int, query: str = "") -> dict[str, Any]:
        local_document = self.get(local_file_id)["metadata"]
        effective = str(query).strip() or self._query_hint(local_document)
        metadata_items = self._yandex.search(effective, limit=25)
        fields = local_document.get("fields") or {}
        local_for_score = {
            "id": int(local_file_id),
            "path": local_document.get("path"),
            "title": fields.get("title"),
            "artists": fields.get("artists") or [],
            "album": fields.get("album"),
            "duration_seconds": (local_document.get("technical") or {}).get("durationSeconds"),
            "tag_title_present": bool(fields.get("title")),
        }
        scorer = MatchScorer()
        ranked: list[tuple[float, YandexTrackMetadata]] = []
        for item in metadata_items:
            provider = {
                "provider_id": "yandex_music", "external_id": item.external_id,
                "payload": self._provider_payload(item),
            }
            score = scorer.score(provider, local_for_score)
            ranked.append((score.confidence, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        items: list[dict[str, Any]] = []
        for index, (score, item) in enumerate(ranked):
            public = self._yandex.public_payload(item, cache_artwork=index < 12)
            public["similarity"] = score
            items.append(public)
        return {"query": effective, "count": len(items), "items": items}

    def yandex_get(self, external_id: str) -> dict[str, Any]:
        metadata = self._yandex.get(external_id)
        return {"track": self._yandex.public_payload(metadata, cache_artwork=True)}

    def compare_yandex(self, local_file_id: int, external_id: str) -> dict[str, Any]:
        local = self.get(local_file_id)["metadata"]
        metadata = self._yandex.get(external_id)
        yandex = self._yandex.public_payload(metadata, cache_artwork=True)
        yandex_fields = dict(yandex["fields"])
        local_fields = dict(local.get("fields") or {})
        rows = []
        for field in BASIC_FIELDS:
            if field == "artwork":
                local_value = bool((local.get("artwork") or {}).get("present"))
                yandex_value = bool((yandex.get("artwork") or {}).get("present"))
            else:
                local_value = local_fields.get(field)
                yandex_value = yandex_fields.get(field)
            rows.append(
                {
                    "field": field,
                    "local": local_value,
                    "yandex": yandex_value,
                    "selected": bool(nonempty(yandex_value)),
                    "available": bool(nonempty(yandex_value)),
                }
            )
        return {"local": local, "yandex": yandex, "rows": rows}

    def _existing_identity(self, local_file_id: int) -> tuple[str | None, str | None]:
        row = self._row(local_file_id)
        return row.get("source_provider_id"), row.get("source_external_id")

    def apply_yandex(
        self,
        local_file_id: int,
        external_id: str,
        selected_fields: list[str],
        *,
        bind_identity: bool,
        confirm: bool,
    ) -> dict[str, Any]:
        if confirm is not True:
            raise MetadataEditorError("Yandex metadata import requires explicit confirmation.")
        metadata = self._yandex.get(external_id)
        y_fields = metadata_fields(metadata)
        selected = set(BASIC_FIELDS if selected_fields is None else selected_fields)
        current_provider, current_external = self._existing_identity(local_file_id)
        if (
            not bind_identity and current_provider == "yandex_music" and current_external
            and str(current_external) != metadata.external_id
        ):
            raise MetadataEditorError(
                "This file already has a different exact Yandex identity. Use 'Apply + Bind' to change identity explicitly."
            )

        patch: dict[str, Any] = {}
        for field in selected:
            if field == "artwork":
                continue
            value = y_fields.get(field)
            # Empty Yandex fields never erase good local metadata implicitly.
            if nonempty(value):
                patch[field] = value

        artwork_data = None
        artwork_mime = None
        if "artwork" in selected:
            art = self._yandex.fetch_artwork(metadata)
            if art is not None:
                artwork_data, artwork_mime = art.data, art.mime

        provenance = None
        if bind_identity:
            provenance = {
                MUSICARK_PROVIDER: "yandex_music",
                MUSICARK_EXTERNAL_ID: metadata.external_id,
                MUSICARK_METADATA_SCHEMA: MUSICARK_METADATA_SCHEMA_VERSION,
                YANDEX_TRACK_ID: metadata.external_id,
                YANDEX_REAL_ID: metadata.real_id,
                YANDEX_ALBUM_ID: metadata.album_id,
                YANDEX_ARTIST_IDS: ",".join(metadata.artist_ids) if metadata.artist_ids else None,
            }

        provider_payload = self._provider_payload(metadata)
        if bind_identity:
            # Exact binding needs a stable provider snapshot even if the selected track
            # is outside the user's current Yandex collection.
            self._identity.cache_provider_track(metadata.external_id, provider_payload)

        result = self.update(
            local_file_id, patch, confirm=True, provenance=provenance,
            artwork_data=artwork_data, artwork_mime=artwork_mime,
        )
        result["yandex"] = {"identity": identity_fields(metadata), "appliedFields": sorted(patch.keys()) + (["artwork"] if artwork_data is not None else [])}
        if bind_identity:
            result["identity"] = self._identity.bind_yandex(
                external_id=metadata.external_id,
                local_file_id=int(local_file_id),
                provider_payload=provider_payload,
            )
            # Refresh the document after EXACT_ID persistence so the UI immediately
            # reflects the user-confirmed identity.
            result["metadata"] = self.get(int(local_file_id))["metadata"]
        else:
            result["identity"] = None

        try:
            result["coverage"] = LibraryCoverageService(
                base_dir=self._base_dir, database_path=self._database_path,
            ).track(metadata.external_id)
        except Exception:  # noqa: BLE001 - track may legitimately be outside active library.
            result["coverage"] = None
        return result
