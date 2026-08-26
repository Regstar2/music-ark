"""External provider HTTP transport with explicit System/Direct/Custom routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

from .credentials import ExternalCredentialStore


class NetworkMode(StrEnum):
    SYSTEM = "system"
    DIRECT = "direct"
    CUSTOM_PROXY = "custom_proxy"


class ProxyScheme(StrEnum):
    SOCKS5 = "socks5"
    HTTP = "http"
    HTTPS = "https"


def _network_mode(value: Any) -> NetworkMode:
    """Resolve current and legacy persisted mode values safely.

    v0.12 exposed `auto` and application-managed `warp`. v1.0 removes both
    release modes, so those saved values migrate to System. Custom never falls
    back to Direct during migration or request execution.
    """
    raw = str(value or "").strip().casefold()
    if raw in {"", "system", "auto", "warp"}:
        return NetworkMode.SYSTEM
    if raw == NetworkMode.DIRECT.value:
        return NetworkMode.DIRECT
    if raw == NetworkMode.CUSTOM_PROXY.value:
        return NetworkMode.CUSTOM_PROXY
    return NetworkMode.SYSTEM


@dataclass(slots=True)
class NetworkSettings:
    mode: NetworkMode = NetworkMode.SYSTEM
    proxy_configured: bool = False
    proxy_scheme: str = ProxyScheme.SOCKS5.value
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 1080
    proxy_username: str = ""

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["mode"] = self.mode.value
        result["proxyConfigured"] = self.proxy_configured
        result["proxyPasswordConfigured"] = False
        return result


class NetworkSettingsStore:
    def __init__(
        self,
        base_dir: Path | None = None,
        credentials: ExternalCredentialStore | None = None,
    ) -> None:
        root = base_dir if base_dir is not None else Path.home()
        self.path = root / ".musicark" / "network_settings.json"
        self.credentials = credentials or ExternalCredentialStore()

    def load(self) -> NetworkSettings:
        if not self.path.is_file():
            return NetworkSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return NetworkSettings()
        return NetworkSettings(
            mode=_network_mode(raw.get("networkMode", "system")),
            proxy_configured=bool(raw.get("proxyConfigured", False)),
            proxy_scheme=str(raw.get("proxyScheme", "socks5")).casefold(),
            proxy_host=str(raw.get("proxyHost", "127.0.0.1")),
            proxy_port=int(raw.get("proxyPort", 1080)),
            proxy_username=str(raw.get("proxyUsername", "")),
        )

    def save(self, payload: dict[str, Any]) -> NetworkSettings:
        current = self.load()
        mode = _network_mode(payload.get("networkMode", current.mode.value))
        scheme = str(payload.get("proxyScheme", current.proxy_scheme)).casefold()
        if scheme not in {item.value for item in ProxyScheme}:
            raise ValueError("Proxy scheme must be http, https or socks5.")
        host = str(payload.get("proxyHost", current.proxy_host)).strip()
        port = int(payload.get("proxyPort", current.proxy_port))
        if not host or not 1 <= port <= 65535:
            raise ValueError("Proxy host/port is invalid.")
        username = str(payload.get("proxyUsername", current.proxy_username)).strip()
        if "proxyPassword" in payload:
            self.credentials.set(
                "proxy_password",
                str(payload.get("proxyPassword") or ""),
            )

        explicit_proxy_flag = payload.get("proxyConfigured")
        if explicit_proxy_flag is None:
            proxy_configured = (
                current.proxy_configured or mode is NetworkMode.CUSTOM_PROXY
            )
        else:
            proxy_configured = bool(explicit_proxy_flag)

        settings = NetworkSettings(
            mode=mode,
            proxy_configured=proxy_configured,
            proxy_scheme=scheme,
            proxy_host=host,
            proxy_port=port,
            proxy_username=username,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "networkMode": settings.mode.value,
                    "proxyConfigured": settings.proxy_configured,
                    "proxyScheme": settings.proxy_scheme,
                    "proxyHost": settings.proxy_host,
                    "proxyPort": settings.proxy_port,
                    "proxyUsername": settings.proxy_username,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return settings

    def public(self) -> dict[str, Any]:
        settings = self.load()
        result = settings.public_dict()
        result["proxyPasswordConfigured"] = (
            self.credentials.get("proxy_password") is not None
        )
        return result


class ExternalNetworkTransport:
    """Apply exactly one selected outbound route for each request."""

    def __init__(
        self,
        settings_store: NetworkSettingsStore,
        *,
        timeout_seconds: float = 6.0,
        route_ttl_seconds: float = 600.0,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        **_legacy_options: Any,
    ) -> None:
        self._settings_store = settings_store
        self._credentials = settings_store.credentials
        self._timeout = httpx.Timeout(
            timeout_seconds,
            connect=min(timeout_seconds, 3.0),
        )
        self._factory = client_factory
        # Kept in the signature for source compatibility with older tests/callers.
        _ = route_ttl_seconds

    def _custom_proxy_url(self, settings: NetworkSettings) -> str:
        user = quote(settings.proxy_username, safe="") if settings.proxy_username else ""
        password = self._credentials.get("proxy_password")
        auth = ""
        if user:
            auth = user
            if password:
                auth += ":" + quote(password, safe="")
            auth += "@"
        return (
            f"{settings.proxy_scheme}://{auth}"
            f"{settings.proxy_host}:{settings.proxy_port}"
        )

    def _route(
        self,
        *,
        force_direct: bool = False,
    ) -> tuple[str, str | None, bool]:
        settings = self._settings_store.load()
        if force_direct or settings.mode is NetworkMode.DIRECT:
            return "direct", None, False
        if settings.mode is NetworkMode.SYSTEM:
            # HTTPX's trust_env path inherits the process/runtime proxy settings.
            # Platform-specific proxy discovery beyond that is not claimed here.
            return "system", None, True
        if settings.mode is NetworkMode.CUSTOM_PROXY:
            if not settings.proxy_configured:
                raise RuntimeError(
                    "Custom proxy mode is selected but no proxy has been configured."
                )
            return "custom_proxy", self._custom_proxy_url(settings), False
        raise RuntimeError("No network route is configured.")

    def request(
        self,
        method: str,
        url: str,
        *,
        force_direct: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        route, proxy, trust_env = self._route(force_direct=force_direct)
        with self._factory(
            proxy=proxy,
            timeout=self._timeout,
            trust_env=trust_env,
            follow_redirects=False,
            http1=True,
            http2=proxy is None,
        ) as client:
            response = client.request(method, url, **kwargs)
        response.extensions["musicark_route"] = route
        return response

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)
