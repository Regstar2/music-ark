from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.providers.models import ProviderPlaylist
from musicark.recovery.models import RecoveryState
from musicark.storage.database import initialize_database
from musicark.storage.recovery_storage import RecoveryStorageRepository
from musicark.upload.batch_service import YandexBatchUploadError, YandexBatchUploadService
from musicark.upload.yandex_service import YandexUploadResult, YandexUploadStatus


class _Audit:
    def __init__(self) -> None:
        self.events = []

    def append(self, event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)


class _Single:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def upload_track(
        self,
        *,
        local_file_id: int,
        playlist_kind: str,
        confirm: bool,
        rights_confirmed: bool,
    ) -> YandexUploadResult:
        self.calls.append((local_file_id, playlist_kind))
        return YandexUploadResult(
            status=YandexUploadStatus.VERIFIED,
            local_file_id=local_file_id,
            playlist_kind=playlist_kind,
            track_id=f"ugc-restored-{local_file_id}",
            read_back_verified=True,
        )


class _Provider:
    def auth_check(self):  # type: ignore[no-untyped-def]
        return {"providerUserId": "owner"}

    def get_playlist(self, external_id: str):  # type: ignore[no-untyped-def]
        return (
            ProviderPlaylist(
                provider_id="yandex_music",
                external_id=str(external_id),
                title="NEDOSTUPNYE",
                track_external_ids=(),
                raw_data={"owner": {"uid": "owner"}},
            ),
            [],
        )


class _Credentials:
    def get_token(self):  # type: ignore[no-untyped-def]
        return "test-token"


class RecoveryRestoreV100Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "musicark.db"
        initialize_database(self.db)
        self.repo = RecoveryStorageRepository(self.db)
        self.repo.set_managed_playlist("unavailable", "77", "НЕДОСТУПНЫЕ")
        self.audit = _Audit()
        self.single = _Single()

    def _insert_recoverable(self, external_id: str, *, local_id: int = 1) -> Path:
        local_path = Path(self.tmp.name) / f"local-{local_id}.mp3"
        local_path.write_bytes(b"ID3-test")
        payload = {
            "provider_id": "yandex_music",
            "external_id": external_id,
            "title": f"Track {external_id}",
            "artists": ["Artist"],
            "album_title": "Album",
            "availability": "unavailable",
        }
        collection_id = f"playlist:{external_id}"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT OR IGNORE INTO local_library_roots(id,path,normalized_path) VALUES(1,?,?)",
                (self.tmp.name, self.tmp.name.casefold()),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO local_audio_files(
                    id, library_root_id, path, normalized_path, file_name, extension,
                    sha256, file_size, codec, metadata_json, title, artists_json, availability
                ) VALUES (?,1,?,?,?,?,?,8,'mp3','{}',?,'[\"Artist\"]','available')
                """,
                (
                    local_id,
                    str(local_path),
                    str(local_path).replace('\\', '/').casefold(),
                    local_path.name,
                    ".mp3",
                    f"sha-{local_id}",
                    f"Track {external_id}",
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_collection_snapshots(
                    provider_id, collection_id, account_json, item_count, refreshed_at,
                    collection_type, external_id, title, owner_name, metadata_json,
                    source_position, active, content_refreshed_at
                ) VALUES ('yandex_music', ?, '{}', 1, datetime('now'),
                          'playlist', ?, 'Playlist', 'owner', '{}', 0, 1, datetime('now'))
                """,
                (collection_id, external_id),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_collection_items(
                    provider_id, collection_id, external_id, position, payload_json
                ) VALUES ('yandex_music', ?, ?, 0, ?)
                """,
                (collection_id, external_id, json.dumps(payload)),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO matching_results(
                    provider_id, external_id, status, local_file_id, confidence, method,
                    score_breakdown_json, reason, matcher_version, provider_fingerprint,
                    local_fingerprint, manual
                ) VALUES('yandex_music',?,'matched',?,1.0,'manual','{}','',1,?,?,1)
                """,
                (external_id, local_id, f"provider-{external_id}", f"local-{local_id}"),
            )
        return local_path

    def _service(self) -> YandexBatchUploadService:
        return YandexBatchUploadService(
            database_path=self.db,
            single_track_service=self.single,  # type: ignore[arg-type]
            repository=self.repo,
            audit_repository=self.audit,  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=_Provider(),  # type: ignore[arg-type]
        )

    def test_recovery_row_restore_revalidates_allows_stale_mapping_and_persists_provenance(self) -> None:
        self._insert_recoverable("10")
        # A previously verified UGC id that is no longer present in the managed
        # playlist must not block an explicit Recovery restore.
        self.repo.upsert_upload_mapping(
            local_file_id=1,
            playlist_kind="77",
            track_id="ugc-old",
            status="verified",
            verified=True,
        )

        result = self._service().execute(
            local_file_ids=[1],
            playlist_kind="77",
            confirm=True,
            rights_confirmed=True,
            batch_id="recovery-test-1",
        )

        self.assertEqual(self.single.calls, [(1, "77")])
        self.assertEqual(result["counts"]["verified"], 1)
        item = result["items"][0]
        self.assertEqual(item["sourceExternalId"], "10")
        self.assertEqual(item["result"]["recoverySourceProvider"], "yandex_music")
        self.assertEqual(item["result"]["recoverySourceExternalId"], "10")
        self.assertEqual(item["result"]["recoveryRole"], "unavailable")
        self.assertEqual(item["result"]["trackId"], "ugc-restored-1")

        mapping = self.repo.upload_mappings([1], "77")[1]
        self.assertEqual(mapping["trackId"], "ugc-restored-1")
        persisted = self.repo.batch("recovery-test-1")
        self.assertIsNotNone(persisted)
        persisted_result = persisted["items"][0]["result"]  # type: ignore[index]
        self.assertEqual(persisted_result["recoverySourceExternalId"], "10")
        self.assertEqual(persisted_result["trackId"], "ugc-restored-1")

        recovery_events = [
            event for event in self.audit.events if event.event_type == "recovery_restore_finished"
        ]
        self.assertEqual(len(recovery_events), 1)
        details = json.loads(recovery_events[0].details)
        self.assertEqual(details["sourceExternalId"], "10")
        self.assertEqual(details["restoredTrackId"], "ugc-restored-1")
        self.assertNotIn("token", recovery_events[0].details.casefold())
        self.assertNotIn(str(Path(self.tmp.name)).casefold(), recovery_events[0].details.casefold())

    def test_explicit_recovery_source_rejects_stale_state_before_upload(self) -> None:
        self._insert_recoverable("20")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            row = conn.execute(
                "SELECT collection_id, payload_json FROM provider_collection_items WHERE external_id='20'"
            ).fetchone()
            payload = json.loads(row[1])
            payload["availability"] = "available"
            conn.execute(
                "UPDATE provider_collection_items SET payload_json=? WHERE collection_id=? AND external_id='20'",
                (json.dumps(payload), row[0]),
            )

        with self.assertRaises(YandexBatchUploadError):
            self._service().execute(
                local_file_ids=[1],
                playlist_kind="77",
                confirm=True,
                rights_confirmed=True,
                batch_id="manual-recovery-test",
                recovery_source_external_id="20",
            )
        self.assertEqual(self.single.calls, [])

    def test_recovery_rejects_missing_local_file_before_upload(self) -> None:
        local_path = self._insert_recoverable("30")
        local_path.unlink()
        with self.assertRaisesRegex(YandexBatchUploadError, "local audio file"):
            self._service().execute(
                local_file_ids=[1],
                playlist_kind="77",
                confirm=True,
                rights_confirmed=True,
                batch_id="manual-recovery-missing-file",
                recovery_source_external_id="30",
            )
        self.assertEqual(self.single.calls, [])

    def test_legacy_recovery_batch_fails_closed_when_source_is_ambiguous(self) -> None:
        self._insert_recoverable("40", local_id=1)
        self._insert_recoverable("41", local_id=1)
        with self.assertRaisesRegex(YandexBatchUploadError, "missing or ambiguous"):
            self._service().execute(
                local_file_ids=[1],
                playlist_kind="77",
                confirm=True,
                rights_confirmed=True,
                batch_id="recovery-ambiguous",
            )
        self.assertEqual(self.single.calls, [])


if __name__ == "__main__":
    unittest.main()
