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
old_block = """        two = ProviderPlaylist(
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
"""
new_block = """        # Existing databases may still contain the retired role. Keep the row
        # non-destructively, but never expose, validate or use it again.
        repo = RecoveryStorageRepository(self.db)
        repo.set_managed_playlist("unavailable", "102", "НЕДОСТУПНЫЕ")
        legacy = ProviderPlaylist(
            provider_id="yandex_music",
            external_id="102",
            title="НЕДОСТУПНЫЕ",
            track_external_ids=(),
            raw_data={"owner": {"uid": "owner"}},
        )
        provider.playlists["102"] = legacy
        service = ManagedPlaylistService(
            self.db,
            repository=repo,
            cache=_Cache([{"externalId": "102", "title": "НЕДОСТУПНЫЕ"}]),  # type: ignore[arg-type]
            credential_store=_Credentials(),  # type: ignore[arg-type]
            provider=provider,  # type: ignore[arg-type]
            audit_repository=_Audit(),  # type: ignore[arg-type]
            creation_enabled=False,
        )
        state = service.state()
        self.assertEqual({item["role"] for item in state["roles"]}, {"censored", "uploaded"})
        self.assertIsNone(service.configured_kind("unavailable"))
        with self.assertRaises(ManagedPlaylistError):
            service.validate_role("unavailable")
        self.assertIn("unavailable", repo.managed_playlists())
"""
text = replace_once(text, old_block, new_block, "replace unavailable managed-role test")
text = replace_once(
    text,
    "        self.assertEqual(len(provider.created), 3)\n",
    "        self.assertEqual(len(provider.created), 2)\n",
    "managed role creation count",
)
recovery_test.write_text(text, encoding="utf-8")

# Keep this old unit fixture scoped to run-one selection; provider setup is
# covered separately by the persistent worker regression suite.
download_test = Path("tests/test_download_bridge_run_task_v07.py")
text = download_test.read_text(encoding="utf-8")
old_run_one = """        with patch.object(bridge, "_prune_user_completed_history", return_value=0):
            result = bridge._user_run_one(service, "selected")  # type: ignore[arg-type]
"""
new_run_one = """        with (
            patch.object(bridge, "_prune_user_completed_history", return_value=0),
            patch.object(bridge, "_configure_user_download_provider", return_value=None),
        ):
            result = bridge._user_run_one(service, "selected")  # type: ignore[arg-type]
"""
text = replace_once(text, old_run_one, new_run_one, "isolate run-one provider fixture")
download_test.write_text(text, encoding="utf-8")

print("Patched issue #54 regression fixtures")
