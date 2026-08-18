"""Offline protocol probe for Yandex Music own-track upload research.

The tool never sends network requests. It can inspect an Electron ASAR/bundle as
raw bytes and sanitize a browser/desktop HAR capture produced while the project
owner performs a normal upload in the official Yandex Music UI.

Reports intentionally contain protocol structure only: methods, redacted URLs,
header names, content types, request field names, JSON key/type shapes and
static structural hints. Credential values, cookies, authorization values, raw
request/response bodies, source-code contexts and file contents are never
copied to the report.
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
_FORM_FIELD_RE = re.compile(
    r"content-disposition:\s*form-data;[^\r\n]*?name=\"([^\"]+)\"(?:;[^\r\n]*?filename=\"([^\"]*)\")?",
    re.IGNORECASE,
)
_FORM_APPEND_RE = re.compile(
    r"\.append\(\s*[\"']([A-Za-z0-9_.:-]{1,80})[\"']\s*,",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_PATH_RE = re.compile(
    r"[\"'](\/[^\"'\s]{0,320}(?:upload|playlist|ugc|track)[^\"'\s]{0,320})[\"']",
    re.IGNORECASE,
)
_HTTP_METHOD_RE = re.compile(
    r"(?:httpClient\.|\bfetch\b[^\r\n]{0,120}\b)(get|post|put|patch|delete)\b",
    re.IGNORECASE,
)
_MIME_RE = re.compile(
    r"\b(?:multipart/form-data|application/octet-stream|audio/(?:mpeg|mp4|ogg|opus|wav|x-wav|flac|aac))\b",
    re.IGNORECASE,
)
_AUDIO_EXTENSION_RE = re.compile(r"\.(?:mp3|flac|m4a|ogg|opus|wav|aac)\b", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]{1,100}\b")
_STATIC_SIGNAL_NAMES = (
    "upload",
    "FormData",
    "multipart/form-data",
    "playlistUuid",
    "api.music.yandex",
    "httpClient.post",
    "httpClient.put",
    "httpClient.patch",
)
_IDENTIFIER_TERMS = ("upload", "track", "playlist", "ugc", "audio", "file", "cover")


def sanitize_url(url: str) -> str:
    """Keep endpoint structure while removing query/fragment values."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid-url>"
    query = urlencode(
        [(name, "<redacted>") for name, _ in parse_qsl(parts.query, keep_blank_values=True)]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


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
        return [] if not value else [_shape(value[0], depth=depth + 1)]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            safe_key = str(key)
            result[safe_key] = (
                "<redacted-field>"
                if _SENSITIVE_KEY_RE.search(safe_key)
                else _shape(child, depth=depth + 1)
            )
        return result
    return type(value).__name__


def _safe_header_summary(headers: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Keep header names and media type only; discard every other value."""
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
    except (TypeError, ValueError):
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
            files.append(
                {"field": field, "filename": f"<redacted>{suffix}" if suffix else "<redacted>"}
            )
    if not fields and not files:
        return None
    return {"field_names": sorted(fields), "files": files}


def _request_body_summary(post_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not post_data:
        return None
    mime_type = str(post_data.get("mimeType") or "").strip() or None
    field_names: list[str] = []
    file_fields: list[dict[str, str]] = []
    for item in post_data.get("params") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name and name not in field_names:
            field_names.append(name)
        file_name = str(item.get("fileName") or "").strip()
        if file_name:
            suffix = Path(file_name).suffix.lower()
            file_fields.append(
                {"field": name, "filename": f"<redacted>{suffix}" if suffix else "<redacted>"}
            )

    text = post_data.get("text")
    result: dict[str, Any] = {"mime_type": mime_type}
    if field_names:
        result["field_names"] = sorted(field_names)
    if file_fields:
        result["files"] = file_fields
    if mime_type and "json" in mime_type.lower():
        json_shape = _json_shape_from_text(text)
        if json_shape is not None:
            result["json_shape"] = json_shape
    multipart = _multipart_summary(text)
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
        except (ValueError, UnicodeError):
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
    report_entries: list[dict[str, Any]] = []

    for entry in raw.get("log", {}).get("entries", []):
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
        response_mime = str(response_content.get("mimeType") or "")
        response_shape = None
        if "json" in response_mime.lower() or (
            response_text and response_text.lstrip().startswith(("{", "["))
        ):
            response_shape = _json_shape_from_text(response_text)

        report_entries.append(
            {
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
        )

    return {
        "format": "musicark-yandex-upload-protocol-report-v2",
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
        if any(
            term in url.lower()
            for term in ("upload", "playlist", "ugc", "track", "api.music.yandex")
        ) and url not in endpoints:
            endpoints.append(url)
    for match in _PATH_RE.finditer(context):
        path = match.group(1)
        if path not in endpoints:
            endpoints.append(path)
    return endpoints[:40]


def _structural_hints(context: str) -> dict[str, Any]:
    lower = context.lower()
    signals = [name for name in _STATIC_SIGNAL_NAMES if name.lower() in lower]
    methods = sorted({match.group(1).upper() for match in _HTTP_METHOD_RE.finditer(context)})
    form_fields = sorted({match.group(1) for match in _FORM_APPEND_RE.finditer(context)})
    mime_types = sorted({match.group(0).lower() for match in _MIME_RE.finditer(context)})
    audio_extensions = sorted({match.group(0).lower() for match in _AUDIO_EXTENSION_RE.finditer(context)})
    identifiers = sorted(
        {
            identifier
            for identifier in _IDENTIFIER_RE.findall(context)
            if any(term in identifier.lower() for term in _IDENTIFIER_TERMS)
            and not _SENSITIVE_KEY_RE.search(identifier)
        }
    )[:120]
    return {
        "signals": signals,
        "http_methods": methods,
        "form_fields": form_fields,
        "mime_types": mime_types,
        "audio_extensions": audio_extensions,
        "related_identifiers": identifiers,
    }


def scan_binary(
    path: Path,
    *,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
    max_hits: int = 1000,
    max_hits_per_keyword: int = 80,
    context_radius: int = 4096,
) -> dict[str, Any]:
    """Search ASAR/bundle bytes while keeping source code and values private."""
    data = path.read_bytes()
    lowered = data.lower()
    keyword_list = list(dict.fromkeys(keywords))
    hits: list[dict[str, Any]] = []
    keyword_counts: dict[str, int] = {}
    truncated_keywords: list[str] = []

    for keyword in keyword_list:
        if len(hits) >= max_hits:
            break
        needle = keyword.encode("utf-8").lower()
        start = 0
        per_keyword_seen: set[str] = set()
        count = 0
        found_more = False

        while len(hits) < max_hits and count < max_hits_per_keyword:
            offset = lowered.find(needle, start)
            if offset < 0:
                break
            left = max(0, offset - context_radius)
            right = min(len(data), offset + len(needle) + context_radius)
            context_bytes = data[left:right]
            digest = hashlib.sha256(context_bytes).hexdigest()[:16]
            if digest not in per_keyword_seen:
                per_keyword_seen.add(digest)
                context = context_bytes.decode("utf-8", errors="replace")
                hints = _structural_hints(context)
                hits.append(
                    {
                        "keyword": keyword,
                        "offset": offset,
                        "context_sha256_16": digest,
                        "candidate_endpoints": _candidate_endpoints(context),
                        **hints,
                    }
                )
                count += 1
            start = offset + max(1, len(needle))

        keyword_counts[keyword] = count
        if count >= max_hits_per_keyword and lowered.find(needle, start) >= 0:
            found_more = True
        if found_more:
            truncated_keywords.append(keyword)

    return {
        "format": "musicark-yandex-upload-protocol-report-v2",
        "source": "binary-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "keywords": keyword_list,
        "keyword_counts": keyword_counts,
        "truncated_keywords": truncated_keywords,
        "hit_count": len(hits),
        "scan": {
            "max_hits": max_hits,
            "max_hits_per_keyword": max_hits_per_keyword,
            "context_radius": context_radius,
        },
        "hits": hits,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
            "ordinary_string_values_included": False,
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

    scan = sub.add_parser(
        "scan-binary",
        help="Search app.asar/bundle bytes for upload-related protocol structure.",
    )
    scan.add_argument(
        "input", type=Path, help="Path to app.asar, yandex-music.asar or another official bundle."
    )
    scan.add_argument("--output", type=Path, default=None, help="Write JSON report instead of stdout.")
    scan.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        default=None,
        help="Search only this keyword; repeat for multiple keywords. Defaults to the built-in research set.",
    )
    scan.add_argument("--max-hits", type=int, default=1000, help="Maximum total distinct contexts.")
    scan.add_argument(
        "--max-hits-per-keyword",
        type=int,
        default=80,
        help="Maximum contexts per keyword so one noisy term cannot starve the rest.",
    )
    scan.add_argument(
        "--context-radius",
        type=int,
        default=4096,
        help="Bytes inspected before and after each match; source text is never emitted.",
    )

    har = sub.add_parser(
        "sanitize-har",
        help="Sanitize a HAR recorded during one normal official upload.",
    )
    har.add_argument("input", type=Path, help="HAR file produced by browser/Electron DevTools.")
    har.add_argument("--output", type=Path, default=None, help="Write sanitized JSON report instead of stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "scan-binary":
        if not args.input.is_file():
            raise SystemExit(f"Input file does not exist: {args.input}")
        keywords = args.keywords if args.keywords else DEFAULT_KEYWORDS
        _write_report(
            scan_binary(
                args.input,
                keywords=keywords,
                max_hits=max(1, args.max_hits),
                max_hits_per_keyword=max(1, args.max_hits_per_keyword),
                context_radius=max(256, args.context_radius),
            ),
            args.output,
        )
        return 0
    if args.command == "sanitize-har":
        if not args.input.is_file():
            raise SystemExit(f"Input HAR does not exist: {args.input}")
        _write_report(sanitize_har(args.input), args.output)
        return 0
    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
