from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.recovery.models import ProviderAvailability, RecoveryState, RecoveryTrack
from musicark.storage.database import initialize_database
from musicark.sync.models import SyncOperationType, SyncScopeType
from musicark.sync.planner import SyncPlanner, _PlanInput


class UnavailableManagedRoleV100Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "musicark.db"
        initialize_database(self.db)

    @staticmethod
    def _unavailable_track() -> RecoveryTrack:
        return RecoveryTrack(
            external_id="42",
            title="Unavailable",
            artists=("Artist",),
            album=None,
            artwork_url=None,
            collections=({"playlistKind": "1", "title": "Playlist"},),
            provider_availability=ProviderAvailability.UNAVAILABLE,
            local_file_id=7,
            local_file_name="local.mp3",
            local_extension=".mp3",
            provider_content_label=None,
            local_content_label=None,
            variant_status="not_checked",
            state=RecoveryState.UNAVAILABLE_LOCAL_AVAILABLE,
        )

    def test_planner_keeps_unavailable_local_copy_informational_only(self) -> None:
        recovery = self._unavailable_track()
        data = _PlanInput(
            scope_type=SyncScopeType.ALL,
            scope_id=None,
            collection_id="",
            target_root_id=None,
            target_folder=None,
            tracks=[
                {
                    "providerId": "yandex_music",
                    "externalId": "42",
                    "coverageStatus": "covered",
                    "userAction": "unreviewed",
                    "variantStatus": "not_checked",
                    "provider": {"title": "Unavailable", "artists": ["Artist"]},
                }
            ],
            recovery={"42": recovery},
            managed={
                "unavailable": {
                    "role": "unavailable",
                    "playlistKind": "legacy-99",
                    "title": "НЕДОСТУПНЫЕ",
                }
            },
            local_fingerprint="local",
            active_downloads={},
        )

        plan = SyncPlanner(self.db)._plan_from_inputs(data, dry_run=True)

        uploads = [
            operation
            for operation in plan.operations
            if operation.operation_type == SyncOperationType.UPLOAD_LOCAL_TO_YANDEX
        ]
        self.assertEqual(uploads, [])
        self.assertEqual(plan.summary["unavailableTracks"], 1)
        self.assertEqual(plan.summary["unavailableRecoverable"], 1)
        self.assertEqual(plan.summary["readyToUpload"], 0)
        self.assertEqual(plan.summary["uploadBlocked"], 0)
        self.assertEqual(plan.summary["uploadByRole"], {"censored": 0})

    def test_flutter_recovery_hides_unavailable_upload_action(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "ui" / "musicark_ui" / "lib" / "sync_page.dart").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("v0111RoleUnavailable", source)
        self.assertNotIn("? 'censored'\n        : 'unavailable'", source)
        self.assertIn("if (censoredRecovery) ...[", source)
        self.assertIn("if (!state.startsWith('censored_')) return;", source)


if __name__ == "__main__":
    unittest.main()
