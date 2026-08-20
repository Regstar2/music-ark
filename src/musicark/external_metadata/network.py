"""Resilient provider HTTP transport with direct/proxy/WARP routing."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import StrEnum
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable
from urllib.parse import quote, urlsplit

import httpx

from .credentials import ExternalCredentialStore


class NetworkMode(StrEnum):
    AUTO = "auto"
    DIRECT = "direct"
    WARP = "warp"
    CUSTOM_PROXY = "custom_proxy"


@dataclass(slots=True)
class NetworkSettings:
    mode: NetworkMode = NetworkMode.AUTO
    proxy_configured: bool = False
    proxy_scheme: str = "socks5"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 1080
    proxy_username: str = ""
    warp_proxy_host: str = "127.0.0.1"
    warp_proxy_port: int = 40000

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["mode"] = self.mode.value
        result["proxyConfigured"] = self.proxy_configured
        result["proxyPasswordConfigured"] = False
        return result


class NetworkSettingsStore:
    def __init__(self, base_dir: Path | None = None, credentials: ExternalCredentialStore | None = None) -> None:
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
        try:
            mode = NetworkMode(str(raw.get("networkMode", "auto")))
        except ValueError:
            mode = NetworkMode.AUTO
        return NetworkSettings(
            mode=mode,
            proxy_configured=bool(raw.get("proxyConfigured", False)),
            proxy_scheme=str(raw.get("proxyScheme", "socks5")),
            proxy_host=str(raw.get("proxyHost", "127.0.0.1")),
            proxy_port=int(raw.get("proxyPort", 1080)),
            proxy_username=str(raw.get("proxyUsername", "")),
            warp_proxy_host=str(raw.get("warpProxyHost", "127.0.0.1")),
            warp_proxy_port=int(raw.get("warpProxyPort", 40000)),
        )

    def save(self, payload: dict[str, Any]) -> NetworkSettings:
        current = self.load()
        mode = NetworkMode(str(payload.get("networkMode", current.mode.value)))
        scheme = str(payload.get("proxyScheme", current.proxy_scheme)).casefold()
        if scheme not in {"http", "https", "socks5"}:
            raise ValueError("Proxy scheme must be http, https or socks5.")
        host = str(payload.get("proxyHost", current.proxy_host)).strip()
        port = int(payload.get("proxyPort", current.proxy_port))
        if not host or not 1 <= port <= 65535:
            raise ValueError("Proxy host/port is invalid.")
        username = str(payload.get("proxyUsername", current.proxy_username)).strip()
        if "proxyPassword" in payload:
            self.credentials.set("proxy_password", str(payload.get("proxyPassword") or ""))
        explicitly_updated = any(
            key in payload
            for key in ("proxyScheme", "proxyHost", "proxyPort", "proxyUsername", "proxyPassword")
        )
        proxy_configured = bool(payload.get("proxyConfigured", current.proxy_configured or explicitly_updated))
        settings = NetworkSettings(
            mode=mode,
            proxy_configured=proxy_configured,
            proxy_scheme=scheme,
            proxy_host=host,
            proxy_port=port,
            proxy_username=username,
            warp_proxy_host=str(payload.get("warpProxyHost", current.warp_proxy_host)).strip() or "127.0.0.1",
            warp_proxy_port=int(payload.get("warpProxyPort", current.warp_proxy_port)),
        )
        if not 1 <= settings.warp_proxy_port <= 65535:
            raise ValueError("WARP proxy port is invalid.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({
                "schemaVersion": 1,
                "networkMode": settings.mode.value,
                "proxyConfigured": settings.proxy_configured,
                "proxyScheme": settings.proxy_scheme,
                "proxyHost": settings.proxy_host,
                "proxyPort": settings.proxy_port,
                "proxyUsername": settings.proxy_username,
                "warpProxyHost": settings.warp_proxy_host,
                "warpProxyPort": settings.warp_proxy_port,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return settings

    def public(self) -> dict[str, Any]:
        settings = self.load()
        result = settings.public_dict()
        result["proxyPasswordConfigured"] = self.credentials.get("proxy_password") is not None
        return result


@dataclass(slots=True)
class _RouteHealth:
    route: str
    expires_at: float


class ExternalNetworkTransport:
    """Use deterministic routes and fallback only for transport-level failures."""

    def __init__(
        self,
        settings_store: NetworkSettingsStore,
        *,
        timeout_seconds: float = 6.0,
        route_ttl_seconds: float = 600.0,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self._settings_store = settings_store
        self._credentials = settings_store.credentials
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))
        self._ttl = route_ttl_seconds
        self._factory = client_factory
        self._health: dict[str, _RouteHealth] = {}
        self._lock = threading.Lock()

    def _custom_proxy_url(self, settings: NetworkSettings) -> str:
        user = quote(settings.proxy_username, safe="") if settings.proxy_username else ""
        password = self._credentials.get("proxy_password")
        auth = ""
        if user:
            auth = user
            if password:
                auth += ":" + quote(password, safe="")
            auth += "@"
        return f"{settings.proxy_scheme}://{auth}{settings.proxy_host}:{settings.proxy_port}"

    @staticmethod
    def _warp_routes(settings: NetworkSettings) -> list[tuple[str, str]]:
        """Return Cloudflare-supported Local Proxy transports in preferred order.

        Modern WARP Proxy mode supports HTTP CONNECT and SOCKS5 on the same
        local listener. Prefer CONNECT because it has proven more interoperable
        with TLS/SNI for MetaBrainz endpoints; keep SOCKS5 as a strict-TLS
        fallback for hosts where CONNECT is unavailable.
        """
        host = settings.warp_proxy_host
        port = settings.warp_proxy_port
        return [
            ("warp_http_connect", f"http://{host}:{port}"),
            ("warp_socks5", f"socks5://{host}:{port}"),
        ]

    def _routes(self, host: str, *, force_direct: bool = False) -> list[tuple[str, str | None]]:
        settings = self._settings_store.load()
        if force_direct:
            return [("direct", None)]
        if settings.mode is NetworkMode.DIRECT:
            return [("direct", None)]
        if settings.mode is NetworkMode.CUSTOM_PROXY:
            if not settings.proxy_configured:
                raise RuntimeError("Custom proxy mode is selected but no proxy has been configured.")
            return [("custom_proxy", self._custom_proxy_url(settings))]
        if settings.mode is NetworkMode.WARP:
            return list(self._warp_routes(settings))

        # AUTO is intentionally cheap: an untouched default proxy field is not a
        # configured route and therefore does not add another failing timeout.
        routes: list[tuple[str, str | None]] = [("direct", None)]
        if settings.proxy_configured:
            routes.append(("custom_proxy", self._custom_proxy_url(settings)))
        routes.extend(self._warp_routes(settings))
        with self._lock:
            healthy = self._health.get(host)
            if healthy and healthy.expires_at > time.monotonic():
                routes.sort(key=lambda item: item[0] != healthy.route)
        return routes

    @staticmethod
    def _is_network_failure(exc: Exception) -> bool:
        return isinstance(
            exc,
            (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadError,
                httpx.ReadTimeout,
                httpx.WriteError,
                httpx.WriteTimeout,
                httpx.CloseError,
                httpx.PoolTimeout,
                httpx.ProxyError,
                httpx.ProtocolError,
            ),
        )

    def request(self, method: str, url: str, *, force_direct: bool = False, **kwargs: Any) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        last: Exception | None = None
        for route, proxy in self._routes(host, force_direct=force_direct):
            try:
                with self._factory(
                    proxy=proxy,
                    timeout=self._timeout,
                    trust_env=False,
                    follow_redirects=False,
                    http1=True,
                    # Use HTTP/1.1 over both WARP proxy transports. This avoids
                    # introducing HTTP/2 state into an already-tunnelled metadata
                    # connection and keeps fallback behavior deterministic.
                    http2=proxy is None,
                ) as client:
                    response = client.request(method, url, **kwargs)
                with self._lock:
                    self._health[host] = _RouteHealth(route, time.monotonic() + self._ttl)
                return response
            except Exception as exc:  # noqa: BLE001 - fallback classification is explicit below.
                last = exc
                if not self._is_network_failure(exc):
                    raise
        if last is not None:
            raise last
        raise RuntimeError("No network route is configured.")

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)
