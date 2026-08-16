from __future__ import annotations

import subprocess
import sys
import unittest


class SyncImportRegressionV08Tests(unittest.TestCase):
    def test_mvp_bridge_import_graph_has_no_sync_storage_cycle(self) -> None:
        code = "\n".join(
            [
                "import musicark.mvp_bridge",
                "from musicark.storage import SyncStorageRepository",
                "from musicark.sync import SyncPlanner, SyncService",
                "assert SyncStorageRepository is not None",
                "assert SyncPlanner is not None",
                "assert SyncService is not None",
            ]
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Fresh-process import failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
