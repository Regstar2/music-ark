"""Offline protocol probe for Yandex Music own-track upload research.

The tool never sends network requests. It can inspect an Electron ASAR/bundle as
raw bytes and sanitize a browser/desktop HAR capture produced while the project
owner performs a normal upload in the official Yandex Music UI.

Only protocol structure is emitted: methods, redacted URLs, header names,
content types, request field names and JSON key/type shapes. Credential values,
cookies, authorization values, raw file contents and ordinary form values are
never copied to the report.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_KEYWORDS = (
    "upload",
    "formdata",
    "multipart",
    "playlist",
    "playlistuuid",
    "ugc",
    "user-track",
    "user_track",
    "api.music.yandex",
    "httpclient.post",
    "httpclient.put",
    "httpclient.patch",
)

_YANDEX_HOST_RE = re.compile(
    r"(^|\.)(?:yandex\.(?:ru|net|com|by|kz)|music\.yandex\.(?:ru|net|com|by|kz))$",
    re.IGNORECASE,
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|sign(?:ature)?|credential)",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}")
_OAUTH_RE = re.compile(r"(?i)(oauth\s+)[A-Za-z0-9._~+/=-]{8,}")
_COOKIE_VALUE_RE = re.compile(r"(?i)(cookie\s*[:=]\s*)[^\r\n\"']+")
_LONG_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_-]{40,}(?![A-Za-z0-9])")
_FORM_FIELD_RE = re.compile(
    r"content-disposition:\s*form-data;[^\r\n]*?name=\"([^\"]+)\"(?:;[^\r\n]*?filename=\"([^\"]*)\")?",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_PATH_RE = re.compile(
    r"[\"'](\/[^\"'\s]{0,220}(?:upload|playlist|ugc|track)[^\"'\s]{0,220})[\"']",
    re.IGNORECASE,
)


def _redact_text(value: str) -> str:
    value = _BEARER_RE.sub(r"\1<redacted>", value)
    value = _OAUTH_RE.sub(r"\1<redacted>", value)
    value = _COOKIE_VALUE_RE.sub(r"\1<redacted>", value)
    value = _LONG_SECRET_RE.sub("<redacted>", value)
    return value


def sanitize_url(url: str) -> str:
    """Keep endpoint structure while removing query/fragment values."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid-url>"
    redacted_query = urlencode([(name, "<redacted>") for name, _ in parse_qsl(parts.query, keep_blank_values=True)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, redacted_query, ""))


def _shape(value: Any, *, depth: int = 0) -> Any:
    """Return JSON key/type structure without preserving scalar values."""
    if depth >= 6:
        return "<max-depth>"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if not value:
            return []
        return [_shape(value[0], depth=depth + 1)]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            safe_key = str(key)
            if _SENSITIVE_KEY_RE.search(safe_key):
                result[safe_key] = "<redacted-field>"
            else:
                result[safe_key] = _shape(child, depth=depth + 1)
        return result
    return type(value).__name__


def _safe_header_summary(headers: Iterable[dict[str, Any]]) -> dict[str, Any]:
    names: list[str] = []
    content_type: str | None = None
    for item in headers:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        lower = name.lower()
        if lower not in names:
            names.append(lower)
        if lower == "content-type":
            raw = str(item.get("value", "")).split(";", 1)[0].strip()
            content_type = raw or None
    return {"names": sorted(names), "content_type": content_type}


def _json_shape_from_text(text: str | None) -> Any | None:
    if not text:
        return None
    try:
        return _shape(json.loads(text))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _multipart_summary(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    fields: list[str] = []
    files: list[dict[str, str]] = []
    for match in _FORM_FIELD_RE.finditer(text):
        field = match.group(1)
        filename = match.group(2)
        if field not in fields:
            fields.append(field)
        if filename:
            suffix = Path(filename).suffix.lower()
            files.append({"field": field, "filename": f"<redacted>{suffix}" if suffix else "<redacted>"})
    if not fields and not files:
        return None
    return {"field_names": sorted(fields), "files": files}


def _request_body_summary(post_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not post_data:
        return None
    mime_type = str(post_data.get("mimeType") or "").strip() or None
    params = post_data.get("params") or []
    field_names: list[str] = []
    file_fields: list[dict[str, str]] = []
    for item in params:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and name not in field_names:
            field_names.append(name)
        file_name = str(item.get("fileName") or "").strip()
        if file_name:
            suffix = Path(file_name).suffix.lower()
            file_fields.append({"field": name, "filename": f"<redacted>{suffix}" if suffix else "<redacted>"})

    text = post_data.get("text")
    json_shape = None
    if mime_type and "json" in mime_type.lower():
        json_shape = _json_shape_from_text(text)
    multipart = _multipart_summary(text)

    result: dict[str, Any] = {"mime_type": mime_type}
    if field_names:
        result["field_names"] = sorted(field_names)
    if file_fields:
        result["files"] = file_fields
    if json_shape is not None:
        result["json_shape"] = json_shape
    if multipart:
        result["multipart"] = multipart
    return result


def _decode_response_text(content: dict[str, Any]) -> str | None:
    text = content.get("text")
    if not isinstance(text, str) or not text:
        return None
    if str(content.get("encoding") or "").lower() == "base64":
        try:
            return base64.b64decode(text, validate=True).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            return None
    return text


def _looks_relevant(method: str, url: str, body: dict[str, Any] | None) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if not _YANDEX_HOST_RE.search(host):
        return False
    haystack = f"{parts.path} {parts.query}".lower()
    if any(keyword in haystack for keyword in ("upload", "playlist", "ugc", "track")):
        return True
    return method.upper() in {"POST", "PUT", "PATCH"} and body is not None


def sanitize_har(path: Path) -> dict[str, Any]:
    """Create a secret-free protocol report from a HAR capture."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    entries = raw.get("log", {}).get("entries", [])
    report_entries: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        method = str(request.get("method") or "GET").upper()
        url = str(request.get("url") or "")
        body = _request_body_summary(request.get("postData"))
        if not _looks_relevant(method, url, body):
            continue

        response_content = response.get("content") or {}
        response_text = _decode_response_text(response_content)
        response_shape = None
        response_mime = str(response_content.get("mimeType") or "")
        if "json" in response_mime.lower() or (response_text and response_text.lstrip().startswith(("{", "["))):
            response_shape = _json_shape_from_text(response_text)

        item: dict[str, Any] = {
            "method": method,
            "url": sanitize_url(url),
            "request_headers": _safe_header_summary(request.get("headers") or []),
            "request_body": body,
            "response": {
                "status": response.get("status"),
                "headers": _safe_header_summary(response.get("headers") or []),
                "mime_type": response_mime or None,
                "json_shape": response_shape,
            },
        }
        report_entries.append(item)

    return {
        "format": "musicark-yandex-upload-protocol-report-v1",
        "source": "sanitized-har",
        "entry_count": len(report_entries),
        "entries": report_entries,
        "safety": {
            "credential_values_included": False,
            "cookie_values_included": False,
            "raw_request_bodies_included": False,
            "raw_response_bodies_included": False,
            "raw_file_contents_included": False,
        },
    }


def _candidate_endpoints(context: str) -> list[str]:
    endpoints: list[str] = []
    for match in _URL_RE.finditer(context):
        url = sanitize_url(match.group(0).rstrip("),;"))
        if any(term in url.lower() for term in ("upload", "playlist", "ugc", "track", "api.music.yandex")):
            endpoints.append(url)
    for match in _PATH_RE.finditer(context):
        path = match.group(1)
        if path not in endpoints:
            endpoints.append(path)
    return endpoints[:20]


def scan_binary(path: Path, *, keywords: Iterable[str] = DEFAULT_KEYWORDS, max_hits: int = 200) -> dict[str, Any]:
    """Search an ASAR/bundle as raw bytes for upload-related source fragments."""
    data = path.read_bytes()
    lowered = data.lower()
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()

    for keyword in keywords:
        needle = keyword.encode("utf-8").lower()
        start = 0
        while len(hits) < max_hits:
            offset = lowered.find(needle, start)
            if offset < 0:
                break
            left = max(0, offset - 420)
            right = min(len(data), offset + len(needle) + 720)
            context = data[left:right].decode("utf-8", errors="replace")
            context = _redact_text(context)
            digest = hashlib.sha256(context.encode("utf-8", errors="replace")).hexdigest()[:16]
            if digest not in seen:
                seen.add(digest)
                hits.append(
                    {
                        "keyword": keyword,
                        "offset": offset,
                        "context_sha256_16": digest,
                        "candidate_endpoints": _candidate_endpoints(context),
                        "context": context,
                    }
                )
            start = offset + max(1, len(needle))
        if len(hits) >= max_hits:
            break

    return {
        "format": "musicark-yandex-upload-protocol-report-v1",
        "source": "binary-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "keywords": list(keywords),
        "hit_count": len(hits),
        "hits": hits,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "raw_file_contents_included": False,
        },
    }


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if output is None:
        print(encoded)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(f"Wrote sanitized report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline/sanitizing Yandex Music upload protocol research tool."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan-binary", help="Search app.asar/bundle bytes for upload-related source fragments.")
    scan.add_argument("input", type=Path, help="Path to app.asar, yandex-music.asar or another official bundle.")
    scan.add_argument("--output", type=Path, default=None, help="Write JSON report instead of stdout.")
    scan.add_argument("--max-hits", type=int, default=200, help="Maximum distinct contexts to include.")

    har = sub.add_parser("sanitize-har", help="Sanitize a HAR recorded during one normal official upload.")
    har.add_argument("input", type=Path, help="HAR file produced by browser/Electron DevTools.")
    har.add_argument("--output", type=Path, default=None, help="Write sanitized JSON report instead of stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "scan-binary":
        if not args.input.is_file():
            raise SystemExit(f"Input file does not exist: {args.input}")
        _write_report(scan_binary(args.input, max_hits=max(1, args.max_hits)), args.output)
        return 0
    if args.command == "sanitize-har":
        if not args.input.is_file():
            raise SystemExit(f"Input HAR does not exist: {args.input}")
        _write_report(sanitize_har(args.input), args.output)
        return 0
    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
