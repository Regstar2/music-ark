"""Compatibility safety tests for the v0.8 sync executor entry point."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from musicark.storage.database import initialize_database
from musicark.sync.safe_execution import SyncSafeExecutor


class SyncSafeExecutorTests(unittest.TestCase):
    def test_confirm_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / ".musicark" / "musicark.db"
            initialize_database(db)
            executor = SyncSafeExecutor(database_path=db, base_dir=root)
            with self.assertRaises(ValueError):
                executor.execute_safe_plan_operations(plan_id=None, confirm=False)

    def test_no_plan_is_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / ".musicark" / "musicark.db"
            initialize_database(db)
            executor = SyncSafeExecutor(database_path=db, base_dir=root)
            with self.assertRaises(ValueError):
                executor.execute_safe_plan_operations(plan_id=None, confirm=True)


if __name__ == "__main__":
    unittest.main()
