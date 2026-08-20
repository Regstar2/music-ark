"""Windows Cloudflare WARP adapter with fail-closed installation and CLI control."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
from typing import Callable
from urllib.parse import urljoin, urlsplit

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

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "version": self.version,
            "installedByMusicArk": self.installed_by_musicark,
            "message": self.message,
        }


class WarpService:
    RELEASES_PAGE = "https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/"
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
        text = f"{result.stdout}\n{result.stderr}".casefold()
        if self._proxy_ready():
            state = WarpState.PROXY_READY
        elif "connecting" in text:
            state = WarpState.CONNECTING
        elif "connected" in text:
            state = WarpState.CONNECTED
        elif "disconnected" in text:
            state = WarpState.DISCONNECTED
        else:
            state = WarpState.INSTALLED if result.returncode == 0 else WarpState.ERROR
        return WarpStatus(state, version=version, installed_by_musicark=self._owned())

    def connect(self) -> WarpStatus:
        result = self._run_cli("connect")
        if result.returncode != 0:
            return WarpStatus(WarpState.ERROR, installed_by_musicark=self._owned(), message="warp-cli connect failed")
        return self.status()

    def disconnect(self) -> WarpStatus:
        result = self._run_cli("disconnect")
        if result.returncode != 0:
            return WarpStatus(WarpState.ERROR, installed_by_musicark=self._owned(), message="warp-cli disconnect failed")
        return self.status()

    def _official_installer_url(self) -> str:
        with self._http_factory(timeout=20, follow_redirects=False, trust_env=False) as client:
            page = client.get(self.RELEASES_PAGE)
        page.raise_for_status()
        # Cloudflare's official releases page contains download links hosted on
        # downloads.cloudflareclient.com. Prefer a Windows MSI link when exposed;
        # otherwise use the page's first Windows stable-download link.
        links = re.findall(r'href=["\']([^"\']+)["\']', page.text, flags=re.IGNORECASE)
        candidates: list[str] = []
        for raw in links:
            url = urljoin(self.RELEASES_PAGE, raw)
            host = (urlsplit(url).hostname or "").casefold()
            if host != self.ALLOWED_DOWNLOAD_HOST:
                continue
            if ".msi" in url.casefold() or "windows" in url.casefold():
                candidates.insert(0, url)
            else:
                candidates.append(url)
        if not candidates:
            raise RuntimeError("Cloudflare stable Windows installer link was not found on the official releases page.")
        return candidates[0]

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
            url = self._official_installer_url()
            host = (urlsplit(url).hostname or "").casefold()
            if host != self.ALLOWED_DOWNLOAD_HOST or urlsplit(url).scheme != "https":
                raise RuntimeError("Cloudflare installer URL failed the trusted-host check.")
            with self._http_factory(timeout=60, follow_redirects=True, trust_env=False) as client:
                response = client.get(url)
            response.raise_for_status()
            if len(response.content) < 1024 * 1024:
                raise RuntimeError("Downloaded Cloudflare installer is unexpectedly small.")
            with tempfile.TemporaryDirectory(prefix="musicark-warp-") as temp_dir:
                path = Path(temp_dir) / "Cloudflare_WARP.msi"
                path.write_bytes(response.content)
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
