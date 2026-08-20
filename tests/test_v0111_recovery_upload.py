from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from musicark.providers.models import ProviderPlaylist, ProviderTrack
from musicark.recovery.managed_playlists import ManagedPlaylistService
from musicark.recovery.models import ProviderAvailability, RecoveryState, RecoveryTrack
from musicark.recovery.service import RecoveryService
from musicark.storage.database import CURRENT_SCHEMA_VERSION, initialize_database
from musicark.storage.recovery_storage import RecoveryStorageRepository
from musicark.upload.batch_service import YandexBatchUploadService
from musicark.upload.yandex_service import YandexUploadResult, YandexUploadStatus


class _Audit:
    def __init__(self) -> None:
        self.events = []

    def append(self, event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)


class _Local:
    def __init__(self, rows: dict[int, dict]) -> None:
        self.rows = rows

    def get_track(self, track_id: int):  # type: ignore[no-untyped-def]
        row = self.rows.get(track_id)
        return dict(row) if row else None


class _Single:
    def __init__(self, statuses: list[YandexUploadStatus], repository=None, cancel_batch_id: str | None = None) -> None:
        self.statuses = list(statuses)
        self.calls: list[tuple[int, str]] = []
        self.repository = repository
        self.cancel_batch_id = cancel_batch_id

    def upload_track(self, *, local_file_id: int, playlist_kind: str, confirm: bool, rights_confirmed: bool):
        self.calls.append((local_file_id, playlist_kind))
        if self.repository is not None and self.cancel_batch_id and len(self.calls) == 1:
            self.repository.request_cancel(self.cancel_batch_id)
        status = self.statuses.pop(0)
        return YandexUploadResult(
            status=status,
            local_file_id=local_file_id,
            playlist_kind=playlist_kind,
            track_id=f"ugc-{local_file_id}",
            read_back_verified=status == YandexUploadStatus.VERIFIED,
        )


class _Provider:
    def __init__(self, playlist_kind: str = "77", member_ids: tuple[str, ...] = ()) -> None:
        self.playlist_kind = playlist_kind
        self.member_ids = member_ids

    def auth_check(self):
        return {"providerUserId": "owner"}

    def get_playlist(self, external_id: str):
        playlist = ProviderPlaylist(
            provider_id="yandex_music",
            external_id=str(external_id),
            title="Target",
            track_external_ids=self.member_ids,
            raw_data={"owner": {"uid": "owner"}},
        )
        tracks = [
            ProviderTrack(
                provider_id="yandex_music",
                external_id=value,
                title=value,
                artists=("Artist",),
            )
            for value in self.member_ids
        ]
        return playlist, tracks


class _Credentials:
    def get_token(self):
        return "test-token"


class _Cache:
    def __init__(self, items: list[dict]) -> None:
        self.items = items

    def list_metadata(self):
        return [dict(value) for value in self.items]


class _ManagedProvider(_Provider):
    def __init__(self, playlists: dict[str, ProviderPlaylist]) -> None:
        self.playlists = playlists
        self.created: list[tuple[str, str]] = []

    def get_playlist(self, external_id: str):
        return self.playlists[str(external_id)], []

    def create_playlist(self, title: str, *, visibility: str = "private"):
        self.created.append((title, visibility))
        kind = str(900 + len(self.created))
        playlist = ProviderPlaylist(
            provider_id="yandex_music",
            external_id=kind,
            title=title,
            track_external_ids=(),
            visibility=visibility,
            raw_data={"owner": {"uid": "owner"}},
        )
        self.playlists[kind] = playlist
        return playlist


class RecoveryAndBatchV0111Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "musicark.db"
        initialize_database(self.db)

    def _insert_playlist_track(
        self,
        external_id: str,
        *,
        availability: str | None,
        playlist_id: str = "playlist:1",
        title: str = "Track",
    ) -> None:
        import json

        payload = {
            "provider_id": "yandex_music",
            "external_id": external_id,
            "title": title,
            "artists": ["Artist"],
            "album_title": "Album",
            "availability": availability,
        }
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_collection_snapshots(
                    provider_id, collection_id, account_json, item_count, refreshed_at,
                    collection_type, external_id, title, owner_name, metadata_json,
                    source_position, active, content_refreshed_at
                ) VALUES ('yandex_music', ?, '{}', 1, datetime('now'),
                          'playlist', ?, 'Playlist', 'owner', '{}', 0, 1, datetime('now'))
                """,
                (playlist_id, playlist_id.removeprefix("playlist:")),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_collection_items(
                    provider_id, collection_id, external_id, position, payload_json
                ) VALUES ('yandex_music', ?, ?, 0, ?)
                """,
                (playlist_id, external_id, json.dumps(payload)),
            )

    def _insert_local_match(self, external_id: str, *, local_id: int = 1, extension: str = ".mp3") -> None:
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO local_library_roots(id,path,normalized_path) VALUES(1,?,?)",
                (self.tmp.name, self.tmp.name.casefold()),
            )
            local_path = Path(self.tmp.name) / f"local-{local_id}{extension}"
            local_path.write_bytes(b"mp3")
            conn.execute(
                """
                INSERT INTO local_audio_files(
                    id, library_root_id, path, normalized_path, file_name, extension,
                    sha256, file_size, codec, metadata_json, title, artists_json, availability
                ) VALUES (?,1,?,?,?,?,?,3,'mp3','{}','Track','[\"Artist\"]','available')
                """,
                (
                    local_id,
                    str(local_path),
                    str(local_path).replace('\\', '/').casefold(),
                    local_path.name,
                    extension,
                    "abc",
                ),
            )
            conn.execute(
                """
                INSERT INTO matching_results(
                    provider_id, external_id, status, local_file_id, confidence, method,
                    score_breakdown_json, reason, matcher_version, provider_fingerprint,
                    local_fingerprint, manual
                ) VALUES('yandex_music',?,'matched',?,1.0,'manual','{}','',1,'p','l',1)
                """,
                (external_id, local_id),
            )

    def test_schema_migrates_additively_to_190(self) -> None:
        with closing(sqlite3.connect(self.db)) as conn, conn:
            for table in (
                "managed_yandex_playlists",
                "yandex_upload_mappings",
                "provider_track_availability_history",
                "yandex_upload_batches",
                "yandex_upload_batch_items",
            ):
                conn.execute(f"DROP TABLE {table}")
            conn.execute(
                "UPDATE app_metadata SET value='1.8.4' WHERE key='schema_version'"
            )
        initialize_database(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute(
                "SELECT value FROM app_metadata WHERE key='schema_version'"
            ).fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        self.assertEqual(version, CURRENT_SCHEMA_VERSION)
        self.assertIn("yandex_upload_mappings", tables)
        self.assertIn("provider_track_availability_history", tables)

    def test_unavailable_is_separate_from_local_coverage(self) -> None:
        self._insert_playlist_track("10", availability="unavailable")
        self._insert_local_match("10")
        tracks = RecoveryService(self.db).tracks(include_healthy=True)
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].provider_availability, ProviderAvailability.UNAVAILABLE)
        self.assertEqual(tracks[0].state, RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE)
        self.assertEqual(tracks[0].local_file_id, 1)

    def test_disappearance_alone_becomes_review_not_unavailable(self) -> None:
        repo = RecoveryStorageRepository(self.db)
        repo.upsert_availability(
            external_id="11",
            availability="available",
            title="Gone",
            artists=["Artist"],
            album=None,
            artwork_url=None,
            collections=[{"playlistKind": "1", "title": "Playlist"}],
        )
        tracks = RecoveryService(self.db).tracks(include_healthy=True)
        gone = next(value for value in tracks if value.external_id == "11")
        self.assertEqual(gone.provider_availability, ProviderAvailability.UNKNOWN)
        self.assertEqual(gone.state, RecoveryState.UNAVAILABLE_NEEDS_REVIEW)

    def test_censorship_requires_explicit_labels(self) -> None:
        self._insert_playlist_track("12", availability="available")
        self._insert_local_match("12")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO provider_track_content_labels(provider_id,external_id,label) VALUES('yandex_music','12','censored')"
            )
            conn.execute(
                "INSERT INTO local_track_content_labels(local_file_id,label) VALUES(1,'original')"
            )
        track = RecoveryService(self.db).tracks(include_healthy=True)[0]
        self.assertEqual(track.state, RecoveryState.CENSORED_ORIGINAL_AVAILABLE)

        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("DELETE FROM provider_track_content_labels")
            conn.execute("DELETE FROM local_track_content_labels")
            conn.execute(
                """
                INSERT INTO track_variant_results(
                    provider_id, external_id, local_file_id, status,
                    metadata_json, variant_reasons_json, altered_segments_json
                ) VALUES('yandex_music','12',1,'altered','{}','[]','[]')
                """
            )
        track = RecoveryService(self.db).tracks(include_healthy=True)[0]
        self.assertEqual(track.state, RecoveryState.CENSORSHIP_NEEDS_REVIEW)

    def test_planner_style_read_does_not_write_availability_history(self) -> None:
        self._insert_playlist_track("13", availability="unavailable")
        service = RecoveryService(self.db)
        result = service.by_external_ids(["13"], persist_history=False)
        self.assertEqual(result["13"].state, RecoveryState.UNAVAILABLE_LOCAL_MISSING)
        with closing(sqlite3.connect(self.db)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM provider_track_availability_history"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_batch_is_sequential_and_delivery_unknown_not_retried(self) -> None:
        repo = RecoveryStorageRepository(self.db)
        single = _Single([YandexUploadStatus.VERIFIED, YandexUploadStatus.DELIVERY_UNKNOWN])
        local = _Local(
            {
                1: {"id": 1, "extension": ".mp3"},
                2: {"id": 2, "extension": ".mp3"},
            }
        )
        service = YandexBatchUploadService(
            database_path=self.db,
            single_track_service=single,  # type: ignore[arg-type]
            repository=repo,
            local_repository=local,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=_Provider(),  # type: ignore[arg-type]
        )
        first = service.execute(
            local_file_ids=[1, 2],
            playlist_kind="77",
            confirm=True,
            rights_confirmed=True,
            batch_id="batch-one",
        )
        self.assertEqual(single.calls, [(1, "77"), (2, "77")])
        self.assertEqual(first["counts"]["verified"], 1)
        self.assertEqual(first["counts"]["deliveryUnknown"], 1)
        self.assertEqual(first["retryableLocalFileIds"], [])
        self.assertEqual(first["manualCheckLocalFileIds"], [2])

        second = service.execute(
            local_file_ids=[2],
            playlist_kind="77",
            confirm=True,
            rights_confirmed=True,
            batch_id="batch-two",
        )
        self.assertEqual(single.calls, [(1, "77"), (2, "77")])
        self.assertEqual(second["counts"]["skipped"], 1)
        self.assertEqual(
            second["items"][0]["result"]["reason"],
            "manual_playlist_check_required",
        )

    def test_batch_cancellation_stops_between_tracks(self) -> None:
        repo = RecoveryStorageRepository(self.db)
        single = _Single(
            [YandexUploadStatus.VERIFIED],
            repository=repo,
            cancel_batch_id="cancel-me",
        )
        local = _Local(
            {
                1: {"id": 1, "extension": ".mp3"},
                2: {"id": 2, "extension": ".mp3"},
            }
        )
        service = YandexBatchUploadService(
            database_path=self.db,
            single_track_service=single,  # type: ignore[arg-type]
            repository=repo,
            local_repository=local,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=_Provider(),  # type: ignore[arg-type]
        )
        result = service.execute(
            local_file_ids=[1, 2],
            playlist_kind="77",
            confirm=True,
            rights_confirmed=True,
            batch_id="cancel-me",
        )
        self.assertEqual(single.calls, [(1, "77")])
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["counts"]["cancelled"], 1)

    def test_managed_playlist_adopts_unique_exact_title_and_never_guesses_duplicate(self) -> None:
        one = ProviderPlaylist(
            provider_id="yandex_music",
            external_id="101",
            title="ЗАГРУЖЕННЫЕ ТРЕКИ",
            track_external_ids=(),
            raw_data={"owner": {"uid": "owner"}},
        )
        provider = _ManagedProvider({"101": one})
        service = ManagedPlaylistService(
            self.db,
            repository=RecoveryStorageRepository(self.db),
            cache=_Cache([{"externalId": "101", "title": "ЗАГРУЖЕННЫЕ ТРЕКИ"}]),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=provider,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            creation_enabled=False,
        )
        result = service.ensure()
        uploaded = next(value for value in result["outcomes"] if value["role"] == "uploaded")
        self.assertEqual(uploaded["state"], "adopted")
        self.assertEqual(service.configured_kind("uploaded"), "101")

        two = ProviderPlaylist(
            provider_id="yandex_music",
            external_id="102",
            title="НЕДОСТУПНЫЕ",
            track_external_ids=(),
            raw_data={"owner": {"uid": "owner"}},
        )
        three = ProviderPlaylist(
            provider_id="yandex_music",
            external_id="103",
            title="НЕДОСТУПНЫЕ",
            track_external_ids=(),
            raw_data={"owner": {"uid": "owner"}},
        )
        provider.playlists.update({"102": two, "103": three})
        service = ManagedPlaylistService(
            self.db,
            repository=RecoveryStorageRepository(self.db),
            cache=_Cache(
                [
                    {"externalId": "102", "title": "НЕДОСТУПНЫЕ"},
                    {"externalId": "103", "title": "НЕДОСТУПНЫЕ"},
                ]
            ),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=provider,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            creation_enabled=False,
        )
        result = service.ensure()
        unavailable = next(value for value in result["outcomes"] if value["role"] == "unavailable")
        self.assertEqual(unavailable["state"], "ambiguous")
        self.assertIsNone(service.configured_kind("unavailable"))

    def test_playlist_creation_is_private_only_when_capability_explicitly_enabled(self) -> None:
        provider = _ManagedProvider({})
        service = ManagedPlaylistService(
            self.db,
            repository=RecoveryStorageRepository(self.db),
            cache=_Cache([]),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=provider,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            creation_enabled=True,
        )
        result = service.ensure(confirm_create=True)
        self.assertEqual(len(provider.created), 3)
        self.assertTrue(all(visibility == "private" for _, visibility in provider.created))
        self.assertTrue(all(item["state"] == "created" for item in result["outcomes"]))


if __name__ == "__main__":
    unittest.main()
