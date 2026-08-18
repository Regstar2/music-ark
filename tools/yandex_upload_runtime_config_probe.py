"""Classify serialized Yandex desktop upload runtime config without values.

This probe is intentionally narrow. It looks only for upload-relevant runtime
configuration keys serialized into packed text members and reports value
*kinds*. Empty strings, safe public enum literals, sanitized Yandex URLs and
safe relative prefixes may be emitted structurally; sensitive/custom token
values never are.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_target_probe as target_probe


TARGET_KEYS = (
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "prefixUrl",
    "clientRemoteType",
)
PUBLIC_ENUMS = {"YandexMusicDesktopApp", "YandexMusicWebNext"}
_TEXT_SUFFIXES = {".js", ".json", ".html", ".htm", ".txt"}
_KEY_VALUE_RE = re.compile(
    r"(?:[\"']?)"
    r"(?P<key>customApiPrefixUrl|customApiToken|apiPrefixUrl|prefixUrl|clientRemoteType)"
    r"(?:[\"']?)\s*[:=]\s*"
    r"(?P<value>null|undefined|true|false|[\"'](?:\\.|[^\"']){0,1000}[\"']|[A-Za-z_$][A-Za-z0-9_$.-]{0,120})",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)",
    re.IGNORECASE,
)
_SAFE_RELATIVE_PREFIX_RE = re.compile(r"^/[A-Za-z0-9_./:-]{0,200}$")


def _is_text_member(path: str) -> bool:
    return Path(path).suffix.lower() in _TEXT_SUFFIXES


def _is_yandex_host(host: str) -> bool:
    clean = host.lower().split(":", 1)[0].rstrip(".")
    return (
        clean == "yandex.ru"
        or clean.endswith(".yandex.ru")
        or clean == "yandex.net"
        or clean.endswith(".yandex.net")
        or clean == "yandex.com"
        or clean.endswith(".yandex.com")
    )


def _safe_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not _is_yandex_host(parsed.netloc):
        return None
    if _SENSITIVE_RE.search(f"{parsed.netloc}{parsed.path}"):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))


def _decode_quoted(value: str) -> tuple[bool, str]:
    if len(value) < 2 or value[0] not in {"\"", "'"} or value[-1] != value[0]:
        return False, value
    if value[0] == '"':
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = value[1:-1]
        return True, decoded if isinstance(decoded, str) else ""
    # Single-quoted JS strings are not JSON. Decode only escaped slash/backslash
    # forms needed to recognize a public prefix; do not expose the result unless
    # it passes the URL/relative-prefix allowlist below.
    scalar = value[1:-1].replace("\\/", "/").replace("\\\\", "\\")
    return True, scalar


def _classify(key: str, raw_value: str) -> dict[str, str]:
    normalized_key = next((item for item in TARGET_KEYS if item.lower() == key.lower()), key)
    value = raw_value.strip()
    lowered = value.lower()
    if lowered == "null":
        return {"key": normalized_key, "kind": "null"}
    if lowered == "undefined":
        return {"key": normalized_key, "kind": "undefined"}
    if lowered in {"true", "false"}:
        return {"key": normalized_key, "kind": "boolean"}

    quoted, scalar = _decode_quoted(value)
    if quoted and scalar == "":
        return {"key": normalized_key, "kind": "empty-string"}

    if normalized_key == "customApiToken":
        return {"key": normalized_key, "kind": "redacted-sensitive-value"}
    if normalized_key == "clientRemoteType":
        if scalar in PUBLIC_ENUMS:
            return {"key": normalized_key, "kind": "public-enum", "value": scalar}
        return {"key": normalized_key, "kind": "string" if quoted else "identifier"}
    if normalized_key in {"customApiPrefixUrl", "apiPrefixUrl", "prefixUrl"}:
        safe = _safe_url(scalar) if quoted else None
        if safe:
            return {"key": normalized_key, "kind": "public-yandex-url", "value": safe}
        if quoted and _SAFE_RELATIVE_PREFIX_RE.fullmatch(scalar) and not _SENSITIVE_RE.search(scalar):
            return {"key": normalized_key, "kind": "public-relative-prefix", "value": scalar}
        return {"key": normalized_key, "kind": "string" if quoted else "identifier"}
    return {"key": normalized_key, "kind": "unknown"}


def _records(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in _KEY_VALUE_RE.finditer(text):
        item = _classify(match.group("key"), match.group("value"))
        if item not in results:
            results.append(item)
    return results[:200]


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001

    members: list[dict[str, Any]] = []
    aggregate: Counter[tuple[str, str, str | None]] = Counter()
    for entry in entries:
        if not _is_text_member(entry["path"]) or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        if not any(key in text for key in TARGET_KEYS):
            continue
        records = _records(text)
        if not records:
            continue
        for record in records:
            aggregate[(record["key"], record["kind"], record.get("value"))] += 1
        members.append(
            {
                "path": entry["path"],
                "size": entry["size"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "records": records,
            }
        )

    summary = [
        {"key": key, "kind": kind, **({"value": value} if value is not None else {}), "member_count": count}
        for (key, kind, value), count in sorted(
            aggregate.items(), key=lambda item: (item[0][0], item[0][1], str(item[0][2]))
        )
    ]
    return {
        "format": "musicark-yandex-upload-runtime-config-report-v1",
        "source": "asar-runtime-config-value-kind-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "summary": summary,
        "members": members[:300],
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "ordinary_string_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify serialized Yandex desktop upload config values safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime-config report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
