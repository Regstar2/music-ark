"""Sanitize Yandex Music desktop runtime traces without persisting secrets.

This module is intentionally transport-agnostic. It accepts CDP/runtime-shaped
objects in memory and emits only request structure: scheme/host/path, query and
header names, status codes, allowlisted client profile labels, invocation names,
and response shapes. Header/query values, cookies, authorization values, signed
URLs, raw bodies, and arbitrary scalar strings are never emitted.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit


TRACE_PREFIX = "__MUSICARK_UPLOAD_TRACE__"
PUBLIC_CLIENT_PROFILES = {"YandexMusicDesktopApp", "YandexMusicWebNext"}
_ALLOWED_AUTH_SOURCES = {"account-oauth", "custom-api-token", "session", "unknown", "none"}
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "token",
    "secret",
    "session",
    "csrf",
    "xsrf",
    "passport",
    "credential",
    "password",
    "signature",
)
_ALLOWED_RUNTIME_FIELDS = {
    "function",
    "moduleId",
    "exportName",
    "methodName",
    "clientRemoteType",
    "customApiPrefixSelected",
    "customApiTokenPathSelected",
    "authorizationSource",
    "argumentShapes",
    "resultShape",
    "timestamp",
}


def _is_sensitive_name(value: str) -> bool:
    lowered = value.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def sanitize_url(value: str) -> dict[str, Any] | None:
    """Return scheme/host/path/query names only for an HTTP(S) URL."""
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query_names: list[str] = []
    for name, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if name and name not in query_names and not _is_sensitive_name(name):
            query_names.append(name)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname or parsed.netloc.split(":", 1)[0],
        "path": parsed.path or "/",
        "queryNames": query_names,
    }


def header_names(headers: Any) -> list[str]:
    """Return normalized header names without values."""
    names: list[str] = []
    if isinstance(headers, dict):
        iterable: Iterable[Any] = headers.keys()
    elif isinstance(headers, list):
        iterable = [item.get("name") for item in headers if isinstance(item, dict)]
    else:
        iterable = []
    for raw in iterable:
        name = str(raw or "").strip().lower()
        if name and name not in names:
            names.append(name)
    return sorted(names)


def _content_type_kind(headers: Any) -> str | None:
    """Classify content type in memory without returning the raw value."""
    if not isinstance(headers, dict):
        return None
    for key, raw in headers.items():
        if str(key).lower() != "content-type":
            continue
        value = str(raw or "").lower()
        if "multipart/form-data" in value:
            return "multipart-form-data"
        if "application/json" in value:
            return "json"
        if value:
            return "other"
    return None


def shape(value: Any, *, depth: int = 0, max_depth: int = 5) -> dict[str, Any]:
    """Describe a value structurally while discarding all scalar string values."""
    if depth >= max_depth:
        return {"type": "truncated"}
    if isinstance(value, dict):
        keys: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            if _is_sensitive_name(key):
                keys[key] = {"type": "redacted-sensitive"}
            else:
                keys[key] = shape(item, depth=depth + 1, max_depth=max_depth)
        return {"type": "object", "keys": keys}
    if isinstance(value, list):
        sample = value[0] if value else None
        return {
            "type": "array",
            "length": len(value),
            "item": shape(sample, depth=depth + 1, max_depth=max_depth) if sample is not None else {"type": "unknown"},
        }
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    return {"type": "string"}


def _safe_auth_source(value: Any) -> str:
    clean = str(value or "unknown").strip().lower()
    return clean if clean in _ALLOWED_AUTH_SOURCES else "unknown"


def sanitize_runtime_payload(payload: Any) -> dict[str, Any] | None:
    """Re-sanitize an instrumentation payload produced inside the renderer."""
    if not isinstance(payload, dict):
        return None
    result: dict[str, Any] = {"event": "runtime"}
    for key in _ALLOWED_RUNTIME_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if key in {"argumentShapes", "resultShape"}:
            result[key] = shape(value)
        elif key == "clientRemoteType":
            clean = str(value or "")
            result[key] = clean if clean in PUBLIC_CLIENT_PROFILES else "unknown"
        elif key == "authorizationSource":
            result[key] = _safe_auth_source(value)
        elif key in {"customApiPrefixSelected", "customApiTokenPathSelected"}:
            result[key] = bool(value)
        elif key == "timestamp":
            result[key] = float(value) if isinstance(value, (int, float)) else None
        else:
            # Invocation/module/export labels are identifiers, not arbitrary values.
            clean = str(value or "")
            result[key] = clean[:160] if clean.replace("_", "").replace("$", "").replace(".", "").isalnum() else "unknown"
    return result


def sanitize_cdp_message(message: Any) -> dict[str, Any] | None:
    """Convert one CDP message into a secret-free trace event."""
    if not isinstance(message, dict):
        return None
    method = message.get("method")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}

    if method == "Network.requestWillBeSent":
        request = params.get("request") if isinstance(params.get("request"), dict) else {}
        url = sanitize_url(str(request.get("url") or ""))
        if not url:
            return None
        names = header_names(request.get("headers"))
        return {
            "event": "request",
            "timestamp": params.get("timestamp") if isinstance(params.get("timestamp"), (int, float)) else None,
            "method": str(request.get("method") or "").upper()[:16],
            **url,
            "headerNames": names,
            "authorization": {"present": "authorization" in names, "source": "unknown" if "authorization" in names else "none"},
            "contentTypeKind": _content_type_kind(request.get("headers")),
        }

    if method == "Network.responseReceived":
        response = params.get("response") if isinstance(params.get("response"), dict) else {}
        url = sanitize_url(str(response.get("url") or ""))
        if not url:
            return None
        names = header_names(response.get("headers"))
        return {
            "event": "response",
            "timestamp": params.get("timestamp") if isinstance(params.get("timestamp"), (int, float)) else None,
            **url,
            "httpStatus": int(response.get("status")) if isinstance(response.get("status"), (int, float)) else None,
            "headerNames": names,
        }

    if method == "Runtime.consoleAPICalled":
        args = params.get("args") if isinstance(params.get("args"), list) else []
        for item in args:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if not isinstance(value, str) or not value.startswith(TRACE_PREFIX):
                continue
            try:
                decoded = json.loads(value[len(TRACE_PREFIX) :])
            except json.JSONDecodeError:
                continue
            return sanitize_runtime_payload(decoded)
    return None


def response_body_shape(body: str, *, base64_encoded: bool = False) -> dict[str, Any]:
    """Return only decoded JSON structure for a response body."""
    raw = body
    if base64_encoded:
        try:
            raw = base64.b64decode(body, validate=True).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            return {"type": "non-json"}
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"type": "non-json"}
    return shape(decoded)


def build_report(events: Iterable[Any]) -> dict[str, Any]:
    sanitized = []
    for event in events:
        item = sanitize_cdp_message(event)
        if item is not None:
            sanitized.append(item)
    return {
        "format": "musicark-yandex-upload-runtime-trace-v1",
        "events": sanitized,
        "safety": {
            "header_values_included": False,
            "query_values_included": False,
            "cookie_values_included": False,
            "authorization_values_included": False,
            "signed_urls_included": False,
            "raw_response_bodies_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize CDP JSONL into a MusicArk upload runtime trace.")
    parser.add_argument("input", type=Path, help="Local JSONL input. Keep raw traces local and delete them after sanitizing.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    report = build_report(events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime trace: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
