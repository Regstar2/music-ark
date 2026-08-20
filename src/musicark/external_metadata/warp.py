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
import time
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
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._database_path = database_path
        self._runner = runner
        self._http_factory = http_client_factory
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._sleep = sleeper
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
        for mode in (
            "WarpWithDnsOverHttps",
            "WarpWithDnsOverTls",
            "DnsOverHttps",
            "DnsOverTls",
            "TunnelOnly",
            "PostureOnly",
        ):
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
            elif service_mode == "WarpProxy":
                message = f"WARP Local proxy mode is active but port {self._proxy_port} is not ready yet."
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

    def _wait_for_proxy(self, latest: WarpStatus | None = None) -> WarpStatus:
        current = latest or self.status()
        for _ in range(40):
            if current.state is WarpState.PROXY_READY:
                return current
            if current.state in {WarpState.ERROR, WarpState.NOT_INSTALLED, WarpState.UNSUPPORTED_VERSION}:
                return current
            self._sleep(0.25)
            current = self.status()
        if current.service_mode == "WarpProxy":
            return WarpStatus(
                WarpState.CONNECTING,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message=f"WARP Local proxy mode is active but port {self._proxy_port} did not become ready in time.",
            )
        return WarpStatus(
            WarpState.UNSUPPORTED_VERSION,
            version=current.version,
            installed_by_musicark=current.installed_by_musicark,
            service_mode=current.service_mode,
            message="warp-cli accepted proxy mode but WarpProxy was not confirmed by client settings.",
        )

    def _configure_proxy_port(self) -> WarpStatus | None:
        """Set the Local Proxy listener port using only commands exposed by this CLI."""
        try:
            proxy_help = self._run_cli("proxy", "--help")
        except (OSError, subprocess.SubprocessError) as exc:
            current = self.status()
            return WarpStatus(
                WarpState.ERROR,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message=f"Failed to inspect warp-cli proxy command: {type(exc).__name__}",
            )
        proxy_help_text = f"{proxy_help.stdout}\n{proxy_help.stderr}".casefold()
        if proxy_help.returncode == 0 and "port" in proxy_help_text:
            result = self._run_cli("proxy", "port", str(self._proxy_port))
            if result.returncode == 0:
                return None
            current = self.status()
            return WarpStatus(
                WarpState.ERROR,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message=f"warp-cli proxy port {self._proxy_port} failed",
            )

        # Older Cloudflare clients exposed the same supported setting as
        # `set-proxy-port`. Only use it if this installed CLI advertises it.
        top_help = self._run_cli("--help")
        top_help_text = f"{top_help.stdout}\n{top_help.stderr}".casefold()
        if top_help.returncode == 0 and "set-proxy-port" in top_help_text:
            result = self._run_cli("set-proxy-port", str(self._proxy_port))
            if result.returncode == 0:
                return None
            current = self.status()
            return WarpStatus(
                WarpState.ERROR,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message=f"warp-cli set-proxy-port {self._proxy_port} failed",
            )

        current = self.status()
        return WarpStatus(
            WarpState.UNSUPPORTED_VERSION,
            version=current.version,
            installed_by_musicark=current.installed_by_musicark,
            service_mode=current.service_mode,
            message="Installed warp-cli does not expose a supported Local Proxy port command.",
        )

    def connect(self) -> WarpStatus:
        """Configure Cloudflare's supported SOCKS5 Local Proxy mode and connect."""
        if not self._cli():
            return WarpStatus(WarpState.NOT_INSTALLED, installed_by_musicark=self._owned())

        try:
            help_result = self._run_cli("mode", "--help")
        except (OSError, subprocess.SubprocessError) as exc:
            return WarpStatus(WarpState.ERROR, installed_by_musicark=self._owned(), message=type(exc).__name__)
        help_text = f"{help_result.stdout}\n{help_result.stderr}".casefold()
        if help_result.returncode != 0 or "proxy" not in help_text:
            current = self.status()
            return WarpStatus(
                WarpState.UNSUPPORTED_VERSION,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message="Installed warp-cli does not expose the supported proxy mode.",
            )

        mode_result = self._run_cli("mode", "proxy")
        if mode_result.returncode != 0:
            current = self.status()
            return WarpStatus(
                WarpState.ERROR,
                version=current.version,
                installed_by_musicark=current.installed_by_musicark,
                service_mode=current.service_mode,
                message="warp-cli mode proxy failed",
            )

        port_error = self._configure_proxy_port()
        if port_error is not None:
            return port_error

        # The current client may apply mode/port changes immediately. Give it a
        # short chance before reconnecting an already-active tunnel.
        current = self.status()
        if current.state is WarpState.PROXY_READY:
            return current
        for _ in range(8):
            self._sleep(0.25)
            current = self.status()
            if current.state is WarpState.PROXY_READY:
                return current

        # Proxy-port changes on some desktop versions are applied only after a
        # reconnect. This action is user-initiated from MusicArk, so perform one
        # bounded reconnect rather than leaving WarpProxy with no listener.
        if current.state in {WarpState.CONNECTED, WarpState.CONNECTING}:
            disconnect_result = self._run_cli("disconnect")
            if disconnect_result.returncode != 0:
                after = self.status()
                return WarpStatus(
                    WarpState.ERROR,
                    version=after.version,
                    installed_by_musicark=after.installed_by_musicark,
                    service_mode=after.service_mode,
                    message="WARP Local Proxy was configured but reconnect could not start (disconnect failed).",
                )
            self._sleep(0.5)
            current = self.status()

        if current.state in {WarpState.DISCONNECTED, WarpState.INSTALLED, WarpState.CONNECTED, WarpState.CONNECTING}:
            result = self._run_cli("connect")
            if result.returncode != 0:
                after = self.status()
                if after.state is WarpState.PROXY_READY:
                    return after
                return WarpStatus(
                    WarpState.ERROR,
                    version=after.version,
                    installed_by_musicark=after.installed_by_musicark,
                    service_mode=after.service_mode,
                    message="warp-cli connect failed",
                )
            return self._wait_for_proxy()

        return self._wait_for_proxy(current)

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