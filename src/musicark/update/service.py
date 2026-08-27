"""Secure update discovery, download verification, and explicit installer launch."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urljoin, urlsplit

from musicark import __version__
from musicark.external_metadata.network import ExternalNetworkTransport, NetworkSettingsStore

from .models import AppVersion, InstallerAsset, UpdateChannel, UpdateError, UpdateErrorCode, UpdateManifest

_DEFAULT_MANIFEST_URL = "https://github.com/Regstar2/music-ark/releases/latest/download/update-manifest.json"
_ALLOWED_EXACT_HOSTS = {"github.com"}
_ALLOWED_HOST_SUFFIXES = (
    ".github.com",
    ".githubusercontent.com",
)
_MAX_REDIRECTS = 5


class UpdateService:
    """Update boundary used by the desktop UI.

    Discovery is read-only. Downloading is explicit and writes only inside the
    MusicArk update cache. Installer execution is a second explicit action and
    never happens as a side effect of checking for updates.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        current_version: str = __version__,
        channel: UpdateChannel = UpdateChannel.STABLE,
        manifest_url: str | None = None,
        transport: ExternalNetworkTransport | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else Path.home()
        self._state_dir = root / ".musicark" / "updates"
        self._current = AppVersion.parse(current_version)
        self._channel = channel
        configured = manifest_url if manifest_url is not None else os.getenv("MUSICARK_UPDATE_MANIFEST_URL")
        self._manifest_url = str(configured or _DEFAULT_MANIFEST_URL).strip()
        self._transport = transport or ExternalNetworkTransport(NetworkSettingsStore(root))

    @staticmethod
    def _trusted_url(url: str) -> bool:
        parsed = urlsplit(str(url).strip())
        if parsed.scheme.casefold() != "https" or parsed.username or parsed.password:
            return False
        host = (parsed.hostname or "").casefold().rstrip(".")
        if not host:
            return False
        return host in _ALLOWED_EXACT_HOSTS or any(host.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES)

    def _validate_url(self, url: str) -> str:
        clean = str(url).strip()
        if not self._trusted_url(clean):
            raise UpdateError(UpdateErrorCode.UNTRUSTED_URL, "Update URL is not an approved HTTPS GitHub host.")
        return clean

    def _get(self, url: str):
        current = self._validate_url(url)
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                response = self._transport.get(current)
            except Exception as exc:  # noqa: BLE001 - normalized at this boundary.
                raise UpdateError(UpdateErrorCode.NETWORK_FAILED, "The update server could not be reached.") from exc
            if response.status_code in {301, 302, 303, 307, 308}:
                location = str(response.headers.get("location", "")).strip()
                if not location:
                    raise UpdateError(UpdateErrorCode.NETWORK_FAILED, "Update redirect did not contain a target URL.")
                current = self._validate_url(urljoin(current, location))
                continue
            return response
        raise UpdateError(UpdateErrorCode.NETWORK_FAILED, "Update request exceeded the redirect limit.")

    def _fetch_manifest(self) -> UpdateManifest:
        if not self._manifest_url:
            raise UpdateError(UpdateErrorCode.CHANNEL_NOT_CONFIGURED, "No update manifest channel is configured.")
        response = self._get(self._manifest_url)
        if response.status_code != 200:
            raise UpdateError(UpdateErrorCode.NETWORK_FAILED, f"Update manifest returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - JSON parser implementation is transport-owned.
            raise UpdateError(UpdateErrorCode.MANIFEST_INVALID, "Update manifest is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise UpdateError(UpdateErrorCode.MANIFEST_INVALID, "Update manifest root must be an object.")
        try:
            manifest = UpdateManifest.from_dict(payload)
        except ValueError as exc:
            raise UpdateError(UpdateErrorCode.MANIFEST_INVALID, str(exc)) from exc
        if manifest.channel is not self._channel:
            raise UpdateError(UpdateErrorCode.MANIFEST_INVALID, "Update manifest channel does not match the selected channel.")
        self._validate_url(manifest.installer.url)
        if manifest.release_notes_url:
            self._validate_url(manifest.release_notes_url)
        return manifest

    def check(self) -> dict[str, Any]:
        manifest = self._fetch_manifest()
        available = manifest.version > self._current
        return {
            "currentVersion": str(self._current),
            "channel": self._channel.value,
            "available": available,
            "latest": manifest.public_dict(),
        }

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _verify_file(cls, path: Path, asset: InstallerAsset) -> None:
        if not path.is_file():
            raise UpdateError(UpdateErrorCode.DOWNLOAD_FAILED, "Prepared installer file is missing.")
        size = path.stat().st_size
        if size != asset.size_bytes:
            raise UpdateError(UpdateErrorCode.SIZE_MISMATCH, "Prepared installer size does not match the signed manifest metadata.")
        if cls._digest(path) != asset.sha256:
            raise UpdateError(UpdateErrorCode.HASH_MISMATCH, "Prepared installer SHA-256 does not match the manifest.")

    def prepare(self) -> dict[str, Any]:
        manifest = self._fetch_manifest()
        if manifest.version <= self._current:
            return {
                "currentVersion": str(self._current),
                "available": False,
                "version": str(manifest.version),
            }

        self._state_dir.mkdir(parents=True, exist_ok=True)
        target = self._state_dir / manifest.installer.file_name
        if target.is_file():
            try:
                self._verify_file(target, manifest.installer)
            except UpdateError:
                target.unlink(missing_ok=True)
            else:
                self._write_prepared(manifest, target)
                return self._prepared_payload(manifest, target, cached=True)

        response = self._get(manifest.installer.url)
        if response.status_code != 200:
            raise UpdateError(UpdateErrorCode.DOWNLOAD_FAILED, f"Installer download returned HTTP {response.status_code}.")
        content = bytes(response.content)
        if len(content) != manifest.installer.size_bytes:
            raise UpdateError(UpdateErrorCode.SIZE_MISMATCH, "Downloaded installer size does not match the manifest.")
        if hashlib.sha256(content).hexdigest() != manifest.installer.sha256:
            raise UpdateError(UpdateErrorCode.HASH_MISMATCH, "Downloaded installer SHA-256 does not match the manifest.")

        temporary = target.with_suffix(target.suffix + ".part")
        temporary.unlink(missing_ok=True)
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self._verify_file(target, manifest.installer)
        self._write_prepared(manifest, target)
        return self._prepared_payload(manifest, target, cached=False)

    def _write_prepared(self, manifest: UpdateManifest, path: Path) -> None:
        marker = self._state_dir / "prepared.json"
        temporary = marker.with_suffix(".json.tmp")
        payload = {
            "manifest": manifest.public_dict(),
            "path": path.name,
        }
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, marker)

    @staticmethod
    def _prepared_payload(manifest: UpdateManifest, path: Path, *, cached: bool) -> dict[str, Any]:
        return {
            "available": True,
            "version": str(manifest.version),
            "fileName": path.name,
            "sha256": manifest.installer.sha256,
            "sizeBytes": manifest.installer.size_bytes,
            "cached": cached,
            "releaseNotesUrl": manifest.release_notes_url,
        }

    def launch_prepared(self, version: str, *, confirm: bool) -> dict[str, Any]:
        if not confirm:
            raise UpdateError(UpdateErrorCode.INSTALLER_LAUNCH_FAILED, "Explicit confirmation is required before launching an installer.")
        if os.name != "nt":
            raise UpdateError(UpdateErrorCode.INSTALLER_LAUNCH_FAILED, "Automatic installer launch is supported only on Windows.")
        requested = AppVersion.parse(version)
        marker = self._state_dir / "prepared.json"
        try:
            raw = json.loads(marker.read_text(encoding="utf-8"))
            manifest = UpdateManifest.from_dict(dict(raw["manifest"]))
            file_name = str(raw["path"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise UpdateError(UpdateErrorCode.INSTALLER_LAUNCH_FAILED, "No valid prepared installer is available.") from exc
        if manifest.version != requested or manifest.version <= self._current:
            raise UpdateError(UpdateErrorCode.INSTALLER_LAUNCH_FAILED, "Prepared installer version is not applicable to this build.")
        path = self._state_dir / file_name
        self._verify_file(path, manifest.installer)
        try:
            process = subprocess.Popen(
                [str(path), "/SP-", "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
                cwd=str(path.parent),
                shell=False,
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError(UpdateErrorCode.INSTALLER_LAUNCH_FAILED, "The verified installer could not be started.") from exc
        return {"launched": True, "version": str(manifest.version), "pid": int(process.pid)}