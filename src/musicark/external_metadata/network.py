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
import requests

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

        # The Flutter form always carries the visible default host/port fields.
        # Merely saving Auto/Direct must therefore not turn 127.0.0.1:1080 into
        # a configured fallback proxy. A proxy becomes configured only when the
        # user explicitly selects Custom Proxy, an existing configuration is
        # already present, or an explicit proxyConfigured value is supplied.
        explicit_proxy_flag = payload.get("proxyConfigured")
        if explicit_proxy_flag is None:
            proxy_configured = current.proxy_configured or mode is NetworkMode.CUSTOM_PROXY
        else:
            proxy_configured = bool(explicit_proxy_flag)

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

    # The WARP local proxy itself is healthy on the user's Windows machine, but
    # HTTPX has intermittently received hostname-mismatched certificates from
    # MetaBrainz hosts through it. requests/urllib3 uses an independent TLS stack
    # and therefore provides a safe, strictly verified CONNECT path before the
    # generic HTTPX/SOCKS fallbacks. No certificate verification is disabled.
    _REQUESTS_CONNECT_HOSTS = {
        "musicbrainz.org",
        "mapper.listenbrainz.org",
        "api.listenbrainz.org",
    }

    def __init__(
        self,
        settings_store: NetworkSettingsStore,
        *,
        timeout_seconds: float = 6.0,
        route_ttl_seconds: float = 600.0,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        requests_session_factory: Callable[[], requests.Session] = requests.Session,
    ) -> None:
        self._settings_store = settings_store
        self._credentials = settings_store.credentials
        self._timeout_seconds = timeout_seconds
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 3.0))
        self._ttl = route_ttl_seconds
        self._factory = client_factory
        self._requests_session_factory = requests_session_factory
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

    @classmethod
    def _warp_routes(cls, settings: NetworkSettings, host: str) -> list[tuple[str, str]]:
        """Return WARP Local Proxy transports in deterministic order.

        MetaBrainz gets an additional requests/urllib3 HTTP CONNECT route first.
        Other hosts keep the generic HTTPX CONNECT -> SOCKS5 path. All routes use
        normal CA and hostname verification.
        """
        proxy_host = settings.warp_proxy_host
        port = settings.warp_proxy_port
        connect_url = f"http://{proxy_host}:{port}"
        routes: list[tuple[str, str]] = []
        if host.casefold() in cls._REQUESTS_CONNECT_HOSTS:
            routes.append(("warp_requests_connect", connect_url))
        routes.extend([
            ("warp_http_connect", connect_url),
            ("warp_socks5", f"socks5://{proxy_host}:{port}"),
        ])
        return routes

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
            return list(self._warp_routes(settings, host))

        routes: list[tuple[str, str | None]] = [("direct", None)]
        if settings.proxy_configured:
            routes.append(("custom_proxy", self._custom_proxy_url(settings)))
        routes.extend(self._warp_routes(settings, host))
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
                requests.exceptions.RequestException,
            ),
        )

    def _request_via_requests(self, method: str, url: str, proxy: str, **kwargs: Any) -> httpx.Response:
        """Use requests/urllib3 for one strict-TLS HTTP CONNECT attempt.

        The rest of the application continues to receive an httpx.Response, so
        provider adapters do not gain a second response contract.
        """
        session = self._requests_session_factory()
        session.trust_env = False
        request_kwargs: dict[str, Any] = {
            "proxies": {"http": proxy, "https": proxy},
            "timeout": (min(self._timeout_seconds, 3.0), self._timeout_seconds),
            "allow_redirects": False,
        }
        for name in ("params", "headers", "json", "data", "files", "cookies", "auth"):
            if name in kwargs:
                request_kwargs[name] = kwargs[name]
        if "content" in kwargs and "data" not in request_kwargs:
            request_kwargs["data"] = kwargs["content"]
        try:
            result = session.request(method, url, **request_kwargs)
        finally:
            session.close()

        response = httpx.Response(
            int(result.status_code),
            headers=dict(result.headers),
            content=result.content,
            request=httpx.Request(method, url),
            extensions={"musicark_route": "warp_requests_connect"},
        )
        return response

    def request(self, method: str, url: str, *, force_direct: bool = False, **kwargs: Any) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        last: Exception | None = None
        for route, proxy in self._routes(host, force_direct=force_direct):
            try:
                if route == "warp_requests_connect":
                    assert proxy is not None
                    response = self._request_via_requests(method, url, proxy, **kwargs)
                else:
                    with self._factory(
                        proxy=proxy,
                        timeout=self._timeout,
                        trust_env=False,
                        follow_redirects=False,
                        http1=True,
                        # Keep proxied metadata traffic on HTTP/1.1. Direct traffic
                        # may still negotiate HTTP/2 where supported.
                        http2=proxy is None,
                    ) as client:
                        response = client.request(method, url, **kwargs)
                    response.extensions["musicark_route"] = route
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
