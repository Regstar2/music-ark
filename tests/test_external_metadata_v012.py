from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

import httpx

from musicark.external_metadata.fingerprint import FingerprintError, FingerprintService
from musicark.external_metadata.models import Confidence, EvidenceType, ExternalMetadataCandidate, MetadataEvidence
from musicark.external_metadata.network import ExternalNetworkTransport, NetworkMode, NetworkSettingsStore
from musicark.storage.database import initialize_database
from musicark.storage.external_metadata_migration import migrate_external_metadata_v012


class _MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str):
        return self.values.get(name)

    def set(self, name: str, value: str | None) -> None:
        if value:
            self.values[name] = value
        else:
            self.values.pop(name, None)


class ExternalMetadataV012Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "musicark.db"
        initialize_database(self.db)
        with sqlite3.connect(self.db) as conn:
            with conn:
                migrate_external_metadata_v012(conn)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_candidate_serialization_keeps_typed_evidence(self) -> None:
        candidate = ExternalMetadataCandidate(
            source="musicbrainz",
            source_display_name="MusicBrainz",
            source_track_id="recording",
            fields={"title": "Track"},
            identities={"musicbrainz_recording_mbid": "recording"},
            evidence=(MetadataEvidence(EvidenceType.EXACT_RECORDING_MBID, "musicbrainz", "recording"),),
            confidence=Confidence.STRONG,
        )
        payload = candidate.as_dict()
        self.assertEqual(payload["confidence"], "strong")
        self.assertEqual(payload["evidence"][0]["type"], "EXACT_RECORDING_MBID")

    def test_external_migration_is_additive_and_idempotent(self) -> None:
        with sqlite3.connect(self.db) as conn:
            with conn:
                self.assertEqual(migrate_external_metadata_v012(conn), "1")
                self.assertEqual(migrate_external_metadata_v012(conn), "1")
            version = conn.execute("SELECT value FROM app_metadata WHERE key='schema_version'").fetchone()[0]
            external = conn.execute("SELECT value FROM app_metadata WHERE key='external_metadata_schema_version'").fetchone()[0]
        self.assertEqual(version, "1.9.0")
        self.assertEqual(external, "1")

    def test_fingerprint_cache_avoids_second_fpcalc_run(self) -> None:
        audio = self.root / "тест.mp3"
        audio.write_bytes(b"audio")
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps({"fingerprint": "abc", "duration": 123.4}), "")

        service = FingerprintService(self.db, executable="fpcalc", runner=runner)
        first = service.fingerprint(7, audio)
        second = service.fingerprint(7, audio)
        self.assertEqual(first.fingerprint, "abc")
        self.assertEqual(second.duration, 123)
        self.assertEqual(len(calls), 1)

    def test_changed_file_invalidates_fingerprint_cache(self) -> None:
        audio = self.root / "track.mp3"
        audio.write_bytes(b"one")
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps({"fingerprint": f"fp{len(calls)}", "duration": 10}), "")

        service = FingerprintService(self.db, executable="fpcalc", runner=runner)
        self.assertEqual(service.fingerprint(9, audio).fingerprint, "fp1")
        audio.write_bytes(b"two-more-bytes")
        self.assertEqual(service.fingerprint(9, audio).fingerprint, "fp2")

    def test_invalid_fpcalc_result_is_typed_failure(self) -> None:
        audio = self.root / "track.mp3"
        audio.write_bytes(b"one")

        def runner(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "not-json", "")

        with self.assertRaises(FingerprintError):
            FingerprintService(self.db, executable="fpcalc", runner=runner).fingerprint(1, audio)

    def test_network_settings_do_not_persist_proxy_password(self) -> None:
        credentials = _MemoryCredentials()
        store = NetworkSettingsStore(self.root, credentials)  # type: ignore[arg-type]
        store.save({
            "networkMode": "custom_proxy",
            "proxyScheme": "socks5",
            "proxyHost": "127.0.0.1",
            "proxyPort": 1080,
            "proxyUsername": "user",
            "proxyPassword": "secret",
        })
        raw = store.path.read_text(encoding="utf-8")
        self.assertNotIn("secret", raw)
        self.assertTrue(store.public()["proxyPasswordConfigured"])

    def test_http_status_does_not_trigger_proxy_fallback(self) -> None:
        credentials = _MemoryCredentials()
        store = NetworkSettingsStore(self.root, credentials)  # type: ignore[arg-type]
        store.save({"networkMode": "auto", "proxyScheme": "http", "proxyHost": "127.0.0.1", "proxyPort": 8080})
        routes = []

        class Client:
            def __init__(self, **kwargs):
                routes.append(kwargs.get("proxy"))
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def request(self, method, url, **kwargs):
                return httpx.Response(404, request=httpx.Request(method, url))

        response = ExternalNetworkTransport(store, client_factory=Client).get("https://example.test/value")  # type: ignore[arg-type]
        self.assertEqual(response.status_code, 404)
        self.assertEqual(routes, [None])

    def test_connect_error_falls_back_from_direct(self) -> None:
        credentials = _MemoryCredentials()
        store = NetworkSettingsStore(self.root, credentials)  # type: ignore[arg-type]
        store.save({"networkMode": NetworkMode.AUTO.value, "proxyScheme": "http", "proxyHost": "127.0.0.1", "proxyPort": 8080})
        routes = []

        class Client:
            def __init__(self, **kwargs): self.proxy = kwargs.get("proxy"); routes.append(self.proxy)
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def request(self, method, url, **kwargs):
                if self.proxy is None:
                    raise httpx.ConnectError("blocked", request=httpx.Request(method, url))
                return httpx.Response(200, request=httpx.Request(method, url))

        response = ExternalNetworkTransport(store, client_factory=Client).get("https://example.test/value")  # type: ignore[arg-type]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(routes[0], None)
        self.assertIn("127.0.0.1:8080", routes[1])


if __name__ == "__main__":
    unittest.main()
