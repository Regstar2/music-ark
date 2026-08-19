"""Inspect the exact ``passportCredentials`` config schema used by stage one.

V34 proves that the upload prefix is built from
``this.config.passportCredentials.host`` with TLD substitution. This probe scans
only occurrences of that schema name and emits safe Yandex HTTP(S) host/template
literals plus allowlisted nested property names. It never emits credentials,
OAuth values, arbitrary strings or raw source contexts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_contract_probe as contract_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_target_probe as target_probe


SCHEMA = "passportCredentials"
_ALLOWLISTED_KEYS = {"passportCredentials", "host", "common", "oauth", "tld", "params", "prefixUrl"}
_TEXT_SUFFIXES = {".js", ".json", ".html", ".htm", ".txt"}
_YANDEX_TEMPLATE_RE = re.compile(
    r"^https?://[A-Za-z0-9._:{}$%+\-]*yandex[A-Za-z0-9._:{}$%+\-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+\-]*)?$",
    re.IGNORECASE,
)


def _is_yandex_host(host: str) -> bool:
    clean = host.lower().split(":", 1)[0].rstrip(".")
    return clean == "yandex.ru" or clean.endswith(".yandex.ru") or clean == "yandex.net" or clean.endswith(".yandex.net") or clean == "yandex.com" or clean.endswith(".yandex.com")


def _safe_url_or_template(value: str) -> str | None:
    clean = value.strip()
    if not clean or "?" in clean or "#" in clean or len(clean) > 300:
        return None
    if "{" in clean or "$" in clean or "%" in clean:
        return clean if _YANDEX_TEMPLATE_RE.fullmatch(clean) else None
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not _is_yandex_host(parsed.netloc):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))


def _safe_literals(fragment: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(fragment):
        if fragment[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(fragment, index)  # noqa: SLF001
        safe = _safe_url_or_template(value)
        if safe and safe not in results:
            results.append(safe)
    return results[:40]


def _allowlisted_keys(fragment: str) -> list[str]:
    found: list[str] = []
    for key in sorted(_ALLOWLISTED_KEYS):
        if re.search(rf"(?:\b|[\"']){re.escape(key)}(?:\b|[\"'])\s*(?::|\.|\?\.)", fragment):
            found.append(key)
    return found


def _schema_objects(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pattern = re.compile(r"(?:[\"']passportCredentials[\"']|\bpassportCredentials\b)\s*:\s*\{")
    for match in pattern.finditer(text):
        start = text.find("{", match.start(), match.end())
        end = contract_probe._find_matching(text, start, "{", "}") if start >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        fragment = text[start : end + 1]
        item = {
            "relation": "object",
            "allowlistedKeys": _allowlisted_keys(fragment),
            "safeYandexHostsOrTemplates": _safe_literals(fragment),
        }
        if item not in results:
            results.append(item)
    return results[:80]


def _schema_reference_windows(text: str, *, radius: int = 1200) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in re.finditer(r"\bpassportCredentials\b", text):
        left = max(0, match.start() - radius)
        right = min(len(text), match.end() + radius)
        fragment = text[left:right]
        item = {
            "relation": "reference-window",
            "allowlistedKeys": _allowlisted_keys(fragment),
            "safeYandexHostsOrTemplates": _safe_literals(fragment),
        }
        if item not in results:
            results.append(item)
    return results[:80]


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
    aggregate: list[str] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() not in _TEXT_SUFFIXES or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        if SCHEMA not in text:
            continue
        objects = _schema_objects(text)
        windows = _schema_reference_windows(text)
        safe_values = []
        for record in [*objects, *windows]:
            for value in record["safeYandexHostsOrTemplates"]:
                if value not in safe_values:
                    safe_values.append(value)
                if value not in aggregate:
                    aggregate.append(value)
        members.append({
            "path": entry["path"],
            "member_sha256": hashlib.sha256(raw).hexdigest(),
            "schemaObjectRecords": objects,
            "schemaReferenceRecords": windows,
            "safeYandexHostsOrTemplates": safe_values[:40],
        })
    return {
        "format": "musicark-yandex-upload-passport-credentials-v1",
        "source": "asar-passportCredentials-host-schema-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "safeYandexHostsOrTemplates": aggregate[:80],
        "members": members[:120],
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "ordinary_string_values_included": False,
            "raw_local_identifiers_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect passportCredentials host schema without values or source leakage.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized passportCredentials report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
