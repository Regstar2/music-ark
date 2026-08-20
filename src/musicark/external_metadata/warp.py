"""Windows Cloudflare WARP adapter with fail-closed installation and CLI control."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
from typing import Callable
from urllib.parse import urlsplit

import httpx

from musicark.storage.external_metadata_migration import migrate_external_metadata_v012


class WarpState(StrEnum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PROXY_READY = "proxy_ready"
    UNSUPPORTED_VERSION = "unsupported_version"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WarpStatus:
    state: WarpState
    version: str = ""
    installed_by_musicark: bool = False
    message: str = ""
    service_mode: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "version": self.version,
            "installedByMusicArk": self.installed_by_musicark,
            "message": self.message,
            "serviceMode": self.service_mode,
        }


class WarpService:
    # This endpoint is the "Download latest stable release" Windows link exposed
    # by Cloudflare's official stable releases page as of 2026-08-20.
    OFFICIAL_WINDOWS_STABLE_URL = "https://downloads.cloudflareclient.com/v1/download/windows/ga"
    ALLOWED_DOWNLOAD_HOST = "downloads.cloudflareclient.com"

    def __init__(
        self,
        database_path: Path,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        http_client_factory: Callable[..., httpx.Client] = httpx.Client,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 40000,
    ) -> None:
        self._database_path = database_path
        self._runner = runner
        self._http_factory = http_client_factory
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        with closing(sqlite3.connect(database_path)) as conn:
            with conn:
                migrate_external_metadata_v012(conn)

    def _cli(self) -> str | None:
        found = shutil.which("warp-cli") or shutil.which("warp-cli.exe")
        if found:
            return found
        if os.name == "nt":
            roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
            for root in roots:
                if not root:
                    continue
                for candidate in (
                    Path(root) / "Cloudflare" / "Cloudflare WARP" / "warp-cli.exe",
                    Path(root) / "Cloudflare" / "Cloudflare One Agent" / "warp-cli.exe",
                ):
                    if candidate.is_file():
                        return str(candidate)
        return None

    def _owned(self) -> bool:
        with closing(sqlite3.connect(self._database_path)) as conn:
            row = conn.execute(
                "SELECT installed_by_musicark FROM network_component_state WHERE component_id='cloudflare_warp'"
            ).fetchone()
        return bool(row and row[0])

    def _mark_owned(self, version: str = "") -> None:
        with closing(sqlite3.connect(self._database_path)) as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO network_component_state(component_id, installed_by_musicark, metadata_json, updated_at)
                    VALUES('cloudflare_warp', 1, ?, datetime('now'))
                    ON CONFLICT(component_id) DO UPDATE SET
                        installed_by_musicark=1,
                        metadata_json=excluded.metadata_json,
                        updated_at=excluded.updated_at
                    """,
                    (json.dumps({"version": version}, ensure_ascii=False),),
                )

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        cli = self._cli()
        if not cli:
            raise FileNotFoundError("warp-cli is not installed.")
        return self._runner(
            [cli, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, shell=False, check=False,
        )

    def _proxy_ready(self) -> bool:
        try:
            with socket.create_connection((self._proxy_host, self._proxy_port), timeout=0.5):
                return True
        except OSError:
            return False

    def _service_mode(self) -> str:
        try:
            result = self._run_cli("settings")
        except (OSError, subprocess.SubprocessError):
            return ""
        if result.returncode != 0:
            return ""
        text = f"{result.stdout}\n{result.stderr}"
        if "WarpProxy" in text:
            return "WarpProxy"
        for mode in ("WarpWithDnsOverHttps", "DnsOverHttps", "TunnelOnly", "PostureOnly"):
            if mode in text:
                return mode
        return ""

    def status(self) -> WarpStatus:
        cli = self._cli()
        if not cli:
            return WarpStatus(WarpState.NOT_INSTALLED, installed_by_musicark=self._owned())
        version = ""
        try:
            version_result = self._run_cli("--version")
            version = (version_result.stdout or version_result.stderr).strip()[:120]
            result = self._run_cli("status")
        except (OSError, subprocess.SubprocessError) as exc:
            return WarpStatus(WarpState.ERROR, version=version, installed_by_musicark=self._owned(), message=type(exc).__name__)
        service_mode = self._service_mode()
        text = f"{result.stdout}\n{result.stderr}".casefold()
        message = ""
        if self._proxy_ready() and service_mode in {"", "WarpProxy"}:
            state = WarpState.PROXY_READY
        elif "connecting" in text:
            state = WarpState.CONNECTING
        elif "connected" in text:
            state = WarpState.CONNECTED
            if service_mode and service_mode != "WarpProxy":
                message = "WARP is connected but Local proxy mode (WarpProxy) is not active."
        elif "disconnected" in text:
            state = WarpState.DISCONNECTED
        else:
            state = WarpState.INSTALLED if result.returncode == 0 else WarpState.ERROR
        return WarpStatus(
            state,
            version=version,
            installed_by_musicark=self._owned(),
            message=message,
            service_mode=service_mode,
        )

    def connect(self) -> WarpStatus:
        result = self._run_cli("connect")
        if result.returncode != 0:
            return WarpStatus(WarpState.ERROR, installed_by_musicark=self._owned(), message="warp-cli connect failed")
        status = self.status()
        # Official documentation confirms that Local proxy mode appears as
        # `WarpProxy` in `warp-cli settings`, but does not document a stable
        # consumer CLI command for switching into that mode. Do not guess one.
        if status.state is WarpState.CONNECTED and status.service_mode not in {"", "WarpProxy"}:
            return WarpStatus(
                WarpState.UNSUPPORTED_VERSION,
                version=status.version,
                installed_by_musicark=status.installed_by_musicark,
                service_mode=status.service_mode,
                message="Cloudflare Local proxy mode must be enabled by a supported client configuration before MusicArk can route through port 40000.",
            )
        return status

    def disconnect(self) -> WarpStatus:
        result = self._run_cli("disconnect")
        if result.returncode != 0:
            return WarpStatus(WarpState.ERROR, installed_by_musicark=self._owned(), message="warp-cli disconnect failed")
        return self.status()

    @staticmethod
    def _trusted_download_url(url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and (parsed.hostname or "").casefold() == WarpService.ALLOWED_DOWNLOAD_HOST
        )

    def _download_installer(self) -> bytes:
        url = self.OFFICIAL_WINDOWS_STABLE_URL
        if not self._trusted_download_url(url):
            raise RuntimeError("Cloudflare installer URL failed the trusted-host check.")
        with self._http_factory(timeout=60, follow_redirects=False, trust_env=False) as client:
            response = client.get(url)
            for _ in range(3):
                if response.status_code not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("location", "")
                if not self._trusted_download_url(location):
                    raise RuntimeError("Cloudflare installer redirect left the trusted download host.")
                response = client.get(location)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().casefold()
        if content_type not in {"application/octet-stream", "application/x-msi", "application/x-msdownload", ""}:
            raise RuntimeError("Cloudflare stable endpoint returned an unexpected content type.")
        if len(response.content) < 1024 * 1024:
            raise RuntimeError("Downloaded Cloudflare installer is unexpectedly small.")
        return bytes(response.content)

    def _verify_signature(self, path: Path) -> bool:
        if os.name != "nt":
            return False
        script = (
            "$s=Get-AuthenticodeSignature -LiteralPath $args[0]; "
            "$o=[pscustomobject]@{Status=$s.Status.ToString();Subject=$s.SignerCertificate.Subject}; "
            "$o | ConvertTo-Json -Compress"
        )
        result = self._runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, shell=False, check=False,
        )
        if result.returncode != 0:
            return False
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False
        return str(payload.get("Status")) == "Valid" and "Cloudflare" in str(payload.get("Subject") or "")

    def install(self) -> WarpStatus:
        if os.name != "nt":
            return WarpStatus(WarpState.UNSUPPORTED_VERSION, message="Automatic WARP installation is implemented for Windows only.")
        before = self.status()
        if before.state is not WarpState.NOT_INSTALLED:
            return before
        try:
            data = self._download_installer()
            with tempfile.TemporaryDirectory(prefix="musicark-warp-") as temp_dir:
                path = Path(temp_dir) / "Cloudflare_WARP.msi"
                path.write_bytes(data)
                if not self._verify_signature(path):
                    raise RuntimeError("Cloudflare installer Authenticode signature is not valid.")
                result = self._runner(
                    ["msiexec.exe", "/i", str(path), "/passive", "/norestart"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, shell=False, check=False,
                )
                if result.returncode not in {0, 3010}:
                    raise RuntimeError(f"Cloudflare installer failed with exit code {result.returncode}.")
            after = self.status()
            if after.state is WarpState.NOT_INSTALLED:
                raise RuntimeError("Cloudflare WARP was not detected after installation.")
            self._mark_owned(after.version)
            return self.status()
        except Exception as exc:  # noqa: BLE001 - public typed state, no URLs/secrets in message.
            return WarpStatus(WarpState.ERROR, installed_by_musicark=False, message=str(exc)[:300])
