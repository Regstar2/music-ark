"""MusicArk v0.8 Controlled Sync integration tests."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from musicark.download.service import DownloadService
from musicark.matching.fingerprints import provider_fingerprint
from musicark.matching.policy import MATCHER_VERSION
from musicark.storage.database import initialize_database
from musicark.storage.matching_storage import MatchingStorageRepository
from musicark.sync.service import SyncService, SyncServiceError

P = "yandex_music"


class ControlledSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / ".musicark" / "musicark.db"
        initialize_database(self.db)
        self.snapshot("liked", "liked", "Мне нравится")

    def snapshot(self, cid: str, kind: str, title: str, *, active: int = 1) -> None:
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                """INSERT OR REPLACE INTO provider_collection_snapshots(
                provider_id,collection_id,account_json,item_count,refreshed_at,
                collection_type,external_id,title,metadata_json,source_position,active)
                VALUES(?,?, '{}',0,datetime('now'),?,?,?,'{}',0,?)""",
                (P, cid, kind, None if cid == "liked" else cid, title, active),
            )

    def member(self, cid: str, eid: str, *, pos: int = 0, storage_id: str | None = None):
        payload = {
            "provider_id": P,
            "external_id": eid,
            "title": f"Track {eid}",
            "artists": ["Artist"],
            "album_title": "Album",
            "duration_seconds": 180.0,
        }
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                "INSERT INTO provider_collection_items(provider_id,collection_id,external_id,position,payload_json) VALUES(?,?,?,?,?)",
                (P, cid, storage_id or eid, pos, json.dumps(payload)),
            )
            c.execute(
                "UPDATE provider_collection_snapshots SET item_count=item_count+1 WHERE provider_id=? AND collection_id=?",
                (P, cid),
            )
        return payload

    def local(self, name: str) -> int:
        path = self.root / name
        path.write_bytes(b"owned-test-audio")
        with closing(sqlite3.connect(self.db)) as c, c:
            cur = c.execute(
                """INSERT INTO local_audio_files(
                path,sha256,file_size,duration_seconds,codec,metadata_json,normalized_path,
                file_name,extension,modified_ns,title,artists_json,album,availability,updated_at)
                VALUES(?,'sha',?,180,'flac','{}',?,?,'.flac',?,?,'[\"Artist\"]','Album','available',datetime('now'))""",
                (str(path), path.stat().st_size, str(path).replace('\\','/').casefold(), path.name, path.stat().st_mtime_ns, path.stem),
            )
            return int(cur.lastrowid)

    def result(self, eid: str, payload: dict[str, object], status: str, local_id: int | None = None) -> None:
        local_fp = MatchingStorageRepository(self.db).local_library_fingerprint()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                """INSERT OR REPLACE INTO matching_results(
                provider_id,external_id,status,local_file_id,confidence,method,reason,
                matcher_version,provider_fingerprint,local_fingerprint,manual,updated_at)
                VALUES(?,?,?,?,?,'automatic','test',?,?,?,0,datetime('now'))""",
                (P, eid, status, local_id, .98 if status == "matched" else 0, MATCHER_VERSION,
                 provider_fingerprint(P, eid, payload), local_fp),
            )
            if status == "matched" and local_id is not None:
                c.execute(
                    """INSERT OR IGNORE INTO track_links(
                    track_id,source_provider_id,source_external_id,local_file_id,confidence,match_method)
                    VALUES(1,?,?,?,.98,'automatic')""",
                    (P, eid, local_id),
                )

    def action(self, eid: str, value: str) -> None:
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                """INSERT INTO provider_track_actions(provider_id,external_id,action) VALUES(?,?,?)
                ON CONFLICT(provider_id,external_id) DO UPDATE SET action=excluded.action,updated_at=datetime('now')""",
                (P, eid, value),
            )

    def target(self, name: str = "downloads") -> Path:
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        DownloadService(base_dir=self.root, database_path=self.db).set_target(str(folder))
        return folder.resolve()

    def service(self) -> SyncService:
        return SyncService(base_dir=self.root, database_path=self.db)

    def test_truth_table_and_no_destructive_operations(self) -> None:
        covered = self.member("liked", "1")
        wanted = self.member("liked", "2", pos=1)
        undecided = self.member("liked", "3", pos=2)
        ignored = self.member("liked", "4", pos=3)
        conflict = self.member("liked", "5", pos=4)
        self.member("liked", "6", pos=5)
        lid = self.local("covered.flac")
        self.result("1", covered, "matched", lid)
        for eid, payload, status in (("2", wanted, "unmatched"),("3", undecided, "unmatched"),("4", ignored, "unmatched"),("5", conflict, "conflict")):
            self.result(eid, payload, status)
        self.action("2", "wanted")
        self.action("4", "ignored")
        plan = self.service().create_plan(scope_type="liked")
        s = plan["summary"]
        self.assertEqual((s["alreadyCovered"],s["readyToDownload"],s["missingUndecided"],s["ignoredMissing"],s["identityReview"],s["notAnalyzed"]),(1,1,1,1,1,1))
        types = [x["type"] for x in plan["operations"]]
        self.assertEqual(types.count("enqueue_download"), 1)
        self.assertEqual(types.count("user_decision_required"), 1)
        self.assertEqual(types.count("review_identity"), 2)
        for forbidden in ("upload_candidate","replace_candidate","update_metadata_candidate","download_track","link_local"):
            self.assertNotIn(forbidden, types)

    def test_variant_policy_is_review_only(self) -> None:
        statuses = ["same","not_checked","uncertain","altered","different_version"]
        pairs = []
        for i, variant in enumerate(statuses):
            eid = str(i + 1)
            payload = self.member("liked", eid, pos=i)
            lid = self.local(f"v{i}.flac")
            pairs.append((eid, payload, lid, variant))
        # Matching freshness uses the whole-library fingerprint for automatic rows.
        # Persist all results only after the fixture's Local Library is complete so
        # earlier rows are not made stale by later test setup.
        for eid, payload, lid, _variant in pairs:
            self.result(eid, payload, "matched", lid)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executemany(
                "INSERT INTO track_variant_results(provider_id,external_id,local_file_id,status) VALUES(?,?,?,?)",
                ((P, eid, lid, variant) for eid, _payload, lid, variant in pairs),
            )
        plan = self.service().create_plan(scope_type="liked")
        self.assertEqual(plan["summary"]["variantIssues"], 3)
        self.assertEqual([x["type"] for x in plan["operations"]].count("review_variant"), 3)
        self.assertFalse(any(x["type"] == "enqueue_download" for x in plan["operations"]))

    def test_scopes_and_duplicate_membership_use_unique_provider_identity(self) -> None:
        self.snapshot("playlist:a", "playlist", "A"); self.snapshot("playlist:b", "playlist", "B")
        payload = self.member("liked", "7")
        self.member("playlist:a", "7", storage_id="7::dup:a")
        self.member("playlist:b", "7", storage_id="7::dup:b")
        self.result("7", payload, "unmatched"); self.action("7", "wanted")
        service = self.service()
        self.assertEqual(service.create_plan(scope_type="all")["summary"]["desiredTracks"], 1)
        self.assertEqual(service.create_plan(scope_type="liked")["summary"]["desiredTracks"], 1)
        self.assertEqual(service.create_plan(scope_type="playlist", scope_id="playlist:a")["summary"]["desiredTracks"], 1)
        self.assertEqual(service.create_plan(scope_type="playlist", scope_id="playlist:b")["summary"]["desiredTracks"], 1)

    def test_existing_queue_does_not_duplicate(self) -> None:
        payload = self.member("liked", "10"); self.result("10", payload, "unmatched"); self.action("10", "wanted")
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("""INSERT INTO download_tasks(id,task_type,source_id,provider_id,status,target_folder,created_at,raw_payload_json,updated_at)
            VALUES('task-10','provider_download','10','yandex_music_download','queued',?,datetime('now'),'{}',datetime('now'))""", (str(self.root),))
        plan = self.service().create_plan(scope_type="liked")
        self.assertEqual((plan["summary"]["readyToDownload"],plan["summary"]["alreadyQueued"]),(0,1))
        op = next(x for x in plan["operations"] if x["type"] == "enqueue_download")
        self.assertEqual((op["status"],op["result"]["reason"]),("skipped","already_queued"))

    def test_covered_wins_over_historical_triage_and_one_download_regression(self) -> None:
        a = self.member("liked", "A"); b = self.member("liked", "B", pos=1)
        self.result("A", a, "unmatched"); self.result("B", b, "unmatched")
        self.action("A", "ignored"); self.action("B", "wanted")
        lid = self.local("downloaded-a.flac")
        self.result("A", a, "matched", lid); self.result("B", b, "unmatched")
        plan = self.service().create_plan(scope_type="liked")
        pending = [x["externalId"] for x in plan["operations"] if x["type"] == "enqueue_download" and x["status"] == "pending"]
        self.assertEqual(pending, ["B"])
        self.assertEqual(plan["summary"]["alreadyCovered"], 1)

    def test_stale_on_triage_change(self) -> None:
        p = self.member("liked", "20"); self.result("20", p, "unmatched"); self.action("20", "wanted")
        s = self.service(); plan = s.create_plan(scope_type="liked"); self.action("20", "ignored")
        self.assertEqual(s.plan(plan["id"])["status"], "stale")

    def test_stale_on_yandex_membership_change(self) -> None:
        p = self.member("liked", "30"); self.result("30", p, "unmatched")
        s = self.service(); plan = s.create_plan(scope_type="liked"); self.member("liked", "31", pos=1)
        self.assertEqual(s.plan(plan["id"])["status"], "stale")

    def test_stale_on_local_library_change(self) -> None:
        p = self.member("liked", "40"); self.result("40", p, "unmatched")
        s = self.service(); plan = s.create_plan(scope_type="liked"); self.local("new.flac")
        self.assertEqual(s.plan(plan["id"])["status"], "stale")

    def test_stale_on_download_target_change(self) -> None:
        p = self.member("liked", "50"); self.result("50", p, "unmatched"); self.action("50", "wanted")
        self.target("one"); s = self.service(); plan = s.create_plan(scope_type="liked")
        s.set_target(str(self.target("two")))
        self.assertEqual(s.plan(plan["id"])["status"], "stale")

    def test_apply_requires_confirmation_and_target(self) -> None:
        p = self.member("liked", "60"); self.result("60", p, "unmatched"); self.action("60", "wanted")
        s = self.service(); plan = s.create_plan(scope_type="liked")
        with self.assertRaises(SyncServiceError) as cm: s.apply(plan["id"], confirm=False)
        self.assertEqual(cm.exception.code, "confirmation_required")
        with self.assertRaises(SyncServiceError) as cm: s.apply(plan["id"], confirm=True)
        self.assertEqual(cm.exception.code, "target_required")

    def test_apply_delegates_to_download_service_is_idempotent_and_does_not_run_queue(self) -> None:
        p = self.member("liked", "70"); self.result("70", p, "unmatched"); self.action("70", "wanted"); self.target()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("""INSERT INTO download_tasks(id,task_type,source_id,provider_id,status,target_folder,created_at,raw_payload_json,updated_at)
            VALUES('unrelated','provider_download','outside','yandex_music_download','queued',?,datetime('now'),'{}',datetime('now'))""", (str(self.root),))
        s = self.service(); plan = s.create_plan(scope_type="liked")
        with patch.object(s._download, "enqueue", return_value={"created":True,"task":{"id":"sync-70"}}) as enqueue:  # noqa: SLF001
            first = s.apply(plan["id"], confirm=True); second = s.apply(plan["id"], confirm=True)
        enqueue.assert_called_once_with("70", provider_id=P)
        self.assertEqual(first["result"]["enqueued"], 1); self.assertTrue(second["repeated"])
        self.assertFalse(first["result"]["downloadsAutoStarted"])
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(c.execute("SELECT status FROM download_tasks WHERE id='unrelated'").fetchone()[0], "queued")

    def test_execution_time_revalidation_skips_already_covered(self) -> None:
        p = self.member("liked", "80"); self.result("80", p, "unmatched"); self.action("80", "wanted"); self.target()
        s = self.service(); plan = s.create_plan(scope_type="liked")
        original = s._coverage.get_track  # noqa: SLF001
        def changed(*, provider_id: str, external_id: str):
            item = dict(original(provider_id=provider_id, external_id=external_id) or {}); item["coverageStatus"] = "covered"; return item
        with patch.object(s._coverage, "get_track", side_effect=changed), patch.object(s._download, "enqueue") as enqueue:  # noqa: SLF001
            result = s.apply(plan["id"], confirm=True)
        enqueue.assert_not_called(); self.assertEqual(result["result"]["items"][0]["reason"], "already_covered")

    def test_legacy_dangerous_plan_is_refused(self) -> None:
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("INSERT INTO sync_plans(id,created_at,dry_run,summary_json,status) VALUES('legacy',datetime('now'),1,'{}','planned')")
            c.execute("""INSERT INTO sync_operations(plan_id,operation_type,entity_id,reason,confidence,is_dangerous,metadata_json)
            VALUES('legacy','upload_candidate','999','old',1,1,'{}')""")
        with self.assertRaises(SyncServiceError) as cm: self.service().apply("legacy", confirm=True)
        self.assertEqual(cm.exception.code, "legacy_plan_unsupported")

    def test_local_only_is_informational_and_playlist_says_outside_scope(self) -> None:
        self.snapshot("playlist:focus", "playlist", "Focus")
        p = self.member("playlist:focus", "90"); linked = self.local("linked.flac"); self.local("outside.flac")
        self.result("90", p, "matched", linked)
        plan = self.service().create_plan(scope_type="playlist", scope_id="playlist:focus")
        ops = [x for x in plan["operations"] if x["type"] == "local_only"]
        self.assertEqual(len(ops), 1); self.assertEqual((ops[0]["reason"],ops[0]["status"]),("outside_selected_scope","informational"))

    def test_rebuild_creates_new_immutable_plan_and_history(self) -> None:
        p = self.member("liked", "91"); self.result("91", p, "unmatched")
        s = self.service(); first = s.create_plan(scope_type="liked"); second = s.create_plan(scope_type="liked")
        self.assertNotEqual(first["id"], second["id"]); self.assertGreaterEqual(len(s.history()["items"]), 2)
        self.assertEqual(s.plan(first["id"])["id"], first["id"])


if __name__ == "__main__":
    unittest.main()
