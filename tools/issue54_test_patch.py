from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


recovery_test = Path("tests/test_v0111_recovery_upload.py")
text = recovery_test.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from musicark.recovery.managed_playlists import ManagedPlaylistService\n",
    "from musicark.recovery.managed_playlists import ManagedPlaylistError, ManagedPlaylistService\n",
    "import ManagedPlaylistError",
)
old_block = '''        two = ProviderPlaylist(\n            provider_id="yandex_music",\n            external_id="102",\n            title="НЕДОСТУПНЫЕ",\n            track_external_ids=(),\n            raw_data={"owner": {"uid": "owner"}},\n        )\n        three = ProviderPlaylist(\n            provider_id="yandex_music",\n            external_id="103",\n            title="НЕДОСТУПНЫЕ",\n            track_external_ids=(),\n            raw_data={"owner": {"uid": "owner"}},\n        )\n        provider.playlists.update({"102": two, "103": three})\n        service = ManagedPlaylistService(\n            self.db,\n            repository=RecoveryStorageRepository(self.db),\n            cache=_Cache(\n                [\n                    {"externalId": "102", "title": "НЕДОСТУПНЫЕ"},\n                    {"externalId": "103", "title": "НЕДОСТУПНЫЕ"},\n                ]\n            ),  # type: ignore[arg-type]\n            credential_store=_Credentials(),  # type: ignore[arg-type]\n            provider=provider,  # type: ignore[arg-type]\n            audit_repository=_Audit(),  # type: ignore[arg-type]\n            creation_enabled=False,\n        )\n        result = service.ensure()\n        unavailable = next(value for value in result["outcomes"] if value["role"] == "unavailable")\n        self.assertEqual(unavailable["state"], "ambiguous")\n        self.assertIsNone(service.configured_kind("unavailable"))\n'''
new_block = '''        # Existing databases may still contain the retired role. Keep the row\n        # non-destructively, but never expose, validate or use it again.\n        repo = RecoveryStorageRepository(self.db)\n        repo.set_managed_playlist("unavailable", "102", "НЕДОСТУПНЫЕ")\n        legacy = ProviderPlaylist(\n            provider_id="yandex_music",\n            external_id="102",\n            title="НЕДОСТУПНЫЕ",\n            track_external_ids=(),\n            raw_data={"owner": {"uid": "owner"}},\n        )\n        provider.playlists["102"] = legacy\n        service = ManagedPlaylistService(\n            self.db,\n            repository=repo,\n            cache=_Cache([{"externalId": "102", "title": "НЕДОСТУПНЫЕ"}]),  # type: ignore[arg-type]\n            credential_store=_Credentials(),  # type: ignore[arg-type]\n            provider=provider,  # type: ignore[arg-type]\n            audit_repository=_Audit(),  # type: ignore[arg-type]\n            creation_enabled=False,\n        )\n        state = service.state()\n        self.assertEqual({item["role"] for item in state["roles"]}, {"censored", "uploaded"})\n        self.assertIsNone(service.configured_kind("unavailable"))\n        with self.assertRaises(ManagedPlaylistError):\n            service.validate_role("unavailable")\n        self.assertIn("unavailable", repo.managed_playlists())\n'''
text = replace_once(text, old_block, new_block, "replace unavailable managed-role test")
text = replace_once(
    text,
    '        self.assertEqual(len(provider.created), 3)\n',
    '        self.assertEqual(len(provider.created), 2)\n',
    "managed role creation count",
)
recovery_test.write_text(text, encoding="utf-8")

# The release branch inherited a #51 unit fixture that predates the resilient\n# provider setup. Keep this test scoped to its intended run-one selection contract.\ndownload_test = Path("tests/test_download_bridge_run_task_v07.py")
text = download_test.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        with patch.object(bridge, "_prune_user_completed_history", return_value=0):\n            result = bridge._user_run_one(service, "selected")  # type: ignore[arg-type]\n''',
    '''        with (\n            patch.object(bridge, "_prune_user_completed_history", return_value=0),\n            patch.object(bridge, "_configure_user_download_provider", return_value=None),\n        ):\n            result = bridge._user_run_one(service, "selected")  # type: ignore[arg-type]\n''',
    "isolate run-one provider fixture",
)
download_test.write_text(text, encoding="utf-8")

print("Patched issue #54 regression fixtures")
