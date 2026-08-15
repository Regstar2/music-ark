from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

from musicark.download.models import DownloadStatus, DownloadTask
from musicark.download.provider import DownloadProviderError, YandexMusicDownloadProvider
from musicark.providers.yandex_music_provider import YandexAuthenticationError


class _Info:
    def __init__(self, bitrate: int, link: str, codec: str = "mp3") -> None:
        self.bitrate_in_kbps = bitrate
        self.codec = codec
        self._link = link

    def get_direct_link(self) -> str:
        return self._link


class _Track:
    def __init__(self, infos: list[_Info]) -> None:
        self._infos = infos

    def get_download_info(self) -> list[_Info]:
        return self._infos


class _Client:
    def __init__(self, tracks: list[_Track]) -> None:
        self._tracks = tracks
        self.requested = None

    def tracks(self, ids):  # type: ignore[no-untyped-def]
        self.requested = list(ids)
        return self._tracks


class _BrokenResponse:
    headers = {"Content-Length": "6"}

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
        del chunk_size
        yield b"abc"
        raise requests.ConnectionError("connection dropped")


class YandexDownloadProviderResolutionTests(unittest.TestCase):
    def test_exact_id_and_best_quality_choose_highest_mp3_bitrate(self) -> None:
        provider = YandexMusicDownloadProvider(token="secure-token")
        client = _Client(
            [
                _Track(
                    [
                        _Info(128, "https://temporary/128"),
                        _Info(320, "https://temporary/320"),
                        _Info(999, "https://temporary/flac", codec="flac"),
                    ]
                )
            ]
        )
        with patch.object(provider, "_build_client", return_value=client):
            link = provider._resolve_direct_link("12345", quality="best")
        self.assertEqual(client.requested, ["12345"])
        self.assertEqual(link, "https://temporary/320")

    def test_numeric_quality_selects_nearest_available_bitrate(self) -> None:
        provider = YandexMusicDownloadProvider(token="secure-token")
        client = _Client([_Track([_Info(128, "128"), _Info(192, "192"), _Info(320, "320")])])
        with patch.object(provider, "_build_client", return_value=client):
            self.assertEqual(provider._resolve_direct_link("7", quality="200"), "192")

    def test_missing_track_has_specific_error(self) -> None:
        provider = YandexMusicDownloadProvider(token="secure-token")
        with patch.object(provider, "_build_client", return_value=_Client([])):
            with self.assertRaises(DownloadProviderError) as cm:
                provider._resolve_direct_link("404")
        self.assertEqual(cm.exception.code, "track_unavailable")

    def test_missing_download_info_has_specific_error(self) -> None:
        provider = YandexMusicDownloadProvider(token="secure-token")
        with patch.object(provider, "_build_client", return_value=_Client([_Track([])])):
            with self.assertRaises(DownloadProviderError) as cm:
                provider._resolve_direct_link("10")
        self.assertEqual(cm.exception.code, "no_download_info")

    def test_authentication_error_is_not_collapsed_to_generic_provider_error(self) -> None:
        provider = YandexMusicDownloadProvider(token="secure-token")
        with patch.object(
            provider,
            "_build_client",
            side_effect=YandexAuthenticationError("expired"),
        ):
            with self.assertRaises(YandexAuthenticationError):
                provider._resolve_direct_link("10")

    def test_invalid_id_is_rejected_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = YandexMusicDownloadProvider(token="secure-token")
            task = DownloadTask(
                task_type="provider_download",
                source_id="not-a-number",
                provider_id="yandex_music_download",
                target_folder=tmp,
                status=DownloadStatus.QUEUED,
            )
            with patch.object(provider, "_resolve_direct_link") as resolve:
                with self.assertRaises(DownloadProviderError) as cm:
                    provider.execute(task)
            self.assertEqual(cm.exception.code, "invalid_track_id")
            resolve.assert_not_called()

    def test_valid_existing_exact_destination_is_reused_without_direct_link_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "Artist - Track [yandex_77].mp3"
            destination.write_bytes(b"existing-audio")
            provider = YandexMusicDownloadProvider(token="secure-token")
            task = DownloadTask(
                task_type="provider_download",
                source_id="77",
                provider_id="yandex_music_download",
                target_folder=str(root),
                status=DownloadStatus.QUEUED,
                raw_payload={
                    "track_id": "77",
                    "target_filename": destination.name,
                },
            )
            with (
                patch.object(provider, "_is_valid_existing_audio", return_value=True),
                patch.object(provider, "_resolve_direct_link") as resolve,
            ):
                result = provider.execute(task)
            self.assertEqual(Path(result.path), destination.resolve())
            resolve.assert_not_called()

    def test_invalid_existing_destination_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "Artist - Track [yandex_88].mp3"
            destination.write_bytes(b"keep-this-unrelated-file")
            provider = YandexMusicDownloadProvider(token="secure-token")
            task = DownloadTask(
                task_type="provider_download",
                source_id="88",
                provider_id="yandex_music_download",
                target_folder=str(root),
                status=DownloadStatus.QUEUED,
                raw_payload={"track_id": "88", "target_filename": destination.name},
            )

            def fake_download(_link: str, output: Path, **_kwargs: object) -> None:
                output.write_bytes(b"downloaded")

            with (
                patch.object(provider, "_is_valid_existing_audio", return_value=False),
                patch.object(provider, "_resolve_direct_link", return_value="temporary-url"),
                patch.object(provider, "_download_to_file", side_effect=fake_download),
            ):
                result = provider.execute(task)

            collision = root / "Artist - Track [yandex_88] (2).mp3"
            self.assertEqual(destination.read_bytes(), b"keep-this-unrelated-file")
            self.assertEqual(collision.read_bytes(), b"downloaded")
            self.assertEqual(Path(result.path), collision.resolve())

    def test_stream_network_failure_removes_part_and_has_network_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "track.mp3"
            provider = YandexMusicDownloadProvider(token="secure-token")
            with patch("musicark.download.provider.requests.get", return_value=_BrokenResponse()):
                with self.assertRaises(DownloadProviderError) as cm:
                    provider._download_to_file("temporary-url", destination)
            self.assertEqual(cm.exception.code, "network_error")
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_name(destination.name + ".part").exists())


if __name__ == "__main__":
    unittest.main()
