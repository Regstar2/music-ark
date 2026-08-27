from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from unittest.mock import patch

from musicark.download import bridge


@dataclass
class _Task:
    id: str
    task_type: str = "provider_download"
    raw_payload: dict[str, object] = field(default_factory=dict)


class _Downloads:
    def __init__(self) -> None:
        self.items = {
            "selected": _Task("selected"),
            "unrelated": _Task("unrelated"),
        }

    def get_task(self, task_id: str) -> _Task:
        return self.items[task_id]


class _Service:
    def __init__(self) -> None:
        self._downloads = _Downloads()
        self.run_calls: list[str] = []

    def tasks(self, *, status: str = "", limit: int = 1000):  # type: ignore[no-untyped-def]
        if status == "running":
            return {"count": 0, "items": []}
        items = [
            {
                "id": "selected",
                "provider": "yandex_music",
                "downloadProvider": "yandex_music_download",
                "status": "queued",
            },
            {
                "id": "unrelated",
                "provider": "yandex_music",
                "downloadProvider": "yandex_music_download",
                "status": "queued",
            },
        ]
        return {"count": len(items), "items": items[:limit]}

    def run_task(self, task_id: str) -> _Task:
        self.run_calls.append(task_id)
        return self._downloads.get_task(task_id)

    def _task_payload(self, task: _Task) -> dict[str, object]:
        return {"id": task.id, "status": "completed"}


class DownloadBridgeRunOneTests(unittest.TestCase):
    def test_run_one_executes_only_selected_task(self) -> None:
        service = _Service()

        # History pruning has its own SQLite-backed coverage. This unit test only
        # verifies that the bridge executes the selected task and does not drain
        # unrelated queued work, so keep storage outside this fake-service fixture.
        with (
            patch.object(bridge, "_prune_user_completed_history", return_value=0),
            patch.object(bridge, "_configure_user_download_provider", return_value=None),
        ):
            result = bridge._user_run_one(service, "selected")  # type: ignore[arg-type]

        self.assertEqual(service.run_calls, ["selected"])
        self.assertEqual(result["task"]["id"], "selected")
        self.assertNotIn("unrelated", service.run_calls)


if __name__ == "__main__":
    unittest.main()
