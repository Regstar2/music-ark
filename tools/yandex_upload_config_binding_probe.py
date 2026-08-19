"""Source-free V8 probe for Yandex UGC upload HTTP-client configuration bindings.

The probe narrows V7 findings to relationships between the UGC upload client,
API-prefix selection, client type, request-header factories and safe client
configuration. It emits structural names and expression kinds only. Credential
values, JavaScript source, ordinary string values and network traffic are never
included.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_contract_probe as contract_probe
import yandex_upload_target_probe as target_probe


DEFAULT_ANCHORS = (
    "UgcUploadHttpClient",
    "getApiPrefixUrl",
    "customApiPrefixUrl",
    "customApiToken",
    "getHeaders",
    "createHttpOptions",
    "createSessionRequestHeaders",
    "createRequestHeaders",
    "clientRemoteType",
    "clientSafeConfig",
    "getClientSafeConfig",
    "YandexMusicDesktopApp",
    "YandexMusicWebNext",
    "prefixUrl",
)

_INTERESTING_KEYS = {
    "customApiPrefixUrl",
    "customApiToken",
    "clientRemoteType",
    "clientSafeConfig",
    "prefixUrl",
    "baseUrl",
    "baseURL",
    "headers",
    "excludeHeaders",
    "withoutHeaders",
    "httpClient",
    "ugc",
}
_INTERESTING_CALLEES = {
    "UgcUploadHttpClient",
    "getApiPrefixUrl",
    "getHeaders",
    "createHttpOptions",
    "createSessionRequestHeaders",
    "createRequestHeaders",
    "getClientSafeConfig",
}
_PROTOCOL_ENUMS = {"YandexMusicDesktopApp", "YandexMusicWebNext"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_MEMBER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+$")
_CALLEE_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
_SENSITIVE_NAME_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|signature|sign$)",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"^https?://[^\s\"'`<>]{3,500}$", re.IGNORECASE)


def _sanitize_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _expression_kind(expression: str) -> dict[str, Any]:
    """Classify an expression without preserving arbitrary scalar values."""
    value = expression.strip()
    if not value:
        return {"kind": "empty"}

    if value in _PROTOCOL_ENUMS:
        return {"kind": "protocol-enum", "name": value}

    if _URL_RE.fullmatch(value.strip("\"'")):
        sanitized = _sanitize_url(value.strip("\"'"))
        return {"kind": "url", "value": sanitized} if sanitized else {"kind": "string"}

    if _IDENTIFIER_RE.fullmatch(value):
        if _SENSITIVE_NAME_RE.search(value):
            return {"kind": "sensitive-identifier", "name": value}
        return {"kind": "identifier", "value": value}

    if _MEMBER_RE.fullmatch(value):
        parts = value.split(".")
        if any(_SENSITIVE_NAME_RE.search(part) for part in parts):
            return {"kind": "sensitive-member", "name": parts[-1]}
        return {"kind": "member", "value": value}

    call_match = re.match(r"^(?:new\s+)?([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\s*\(", value)
    if call_match:
        callee = call_match.group(1)
        if _SENSITIVE_NAME_RE.search(callee):
            return {"kind": "sensitive-call", "name": callee.split(".")[-1]}
        return {"kind": "call", "callee": callee}

    if value.startswith("{"):
        return {"kind": "object"}
    if value.startswith("["):
        return {"kind": "array"}
    if value in {"true", "false"}:
        return {"kind": "boolean"}
    if value == "null":
        return {"kind": "null"}
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return {"kind": "number"}
    if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
        return {"kind": "string"}
    return {"kind": "expression"}


def _find_top_level_colon(text: str) -> int | None:
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char in "([{":
            stack.append(char)
            continue
        if char in ")]}" and stack and stack[-1] == pairs[char]:
            stack.pop()
            continue
        if char == ":" and not stack:
            return index
    return None


def _interesting_object_bindings(fragment: str, *, prefix: str = "") -> list[dict[str, Any]]:
    value = fragment.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return []
    results: list[dict[str, Any]] = []
    for part in contract_probe._split_top_level(value[1:-1]):  # noqa: SLF001
        if part.startswith("..."):
            continue
        colon = _find_top_level_colon(part)
        if colon is None:
            continue
        raw_key = part[:colon].strip().strip("\"'")
        rhs = part[colon + 1 :].strip()
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$-]*", raw_key):
            continue
        path = f"{prefix}.{raw_key}" if prefix else raw_key
        if raw_key in _INTERESTING_KEYS:
            classification = (
                {"kind": "redacted-sensitive-value"}
                if _SENSITIVE_NAME_RE.search(raw_key)
                else _expression_kind(rhs)
            )
            results.append({"path": path, "value": classification})
        if rhs.startswith("{") and rhs.endswith("}"):
            results.extend(_interesting_object_bindings(rhs, prefix=path))
    return results


def _all_interesting_object_bindings(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        end = contract_probe._find_matching(text, index, "{", "}")  # noqa: SLF001
        if end is None:
            continue
        for item in _interesting_object_bindings(text[index : end + 1]):
            if item not in results:
                results.append(item)
    return results[:240]


def _call_relations(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?:new\s+)?([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\s*\("
    )
    for match in pattern.finditer(text):
        callee = match.group(1)
        short = callee.split(".")[-1]
        if short not in _INTERESTING_CALLEES:
            continue
        open_paren = text.find("(", match.start(), match.end())
        end = contract_probe._find_matching(text, open_paren, "(", ")")  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(text[open_paren + 1 : end])  # noqa: SLF001
        relation = {
            "callee": short,
            "argument_kinds": [_expression_kind(arg) for arg in args[:12]],
        }
        if relation not in results:
            results.append(relation)
    return results[:120]


def _anchor_presence(text: str, anchors: Iterable[str]) -> list[str]:
    return [anchor for anchor in anchors if re.search(re.escape(anchor), text, re.IGNORECASE)]


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def build_report(path: Path, offsets: Iterable[int], *, anchors: Iterable[str] = DEFAULT_ANCHORS) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    anchors_list = list(dict.fromkeys(str(value) for value in anchors if str(value)))
    data_start, mappings = target_probe.locate_members(path, offsets_list)

    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(
                key,
                {
                    "path": member["path"],
                    "size": member["size"],
                    "absolute_start": member["absolute_start"],
                    "triggering_offsets": [],
                },
            )
            item["triggering_offsets"].append(mapping["offset"])

    members: list[dict[str, Any]] = []
    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        members.append(
            {
                **member,
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "anchors_present": _anchor_presence(text, anchors_list),
                "object_bindings": _all_interesting_object_bindings(text),
                "call_relations": _call_relations(text),
            }
        )

    return {
        "format": "musicark-yandex-upload-config-binding-report-v1",
        "source": "asar-upload-config-binding-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "anchors": anchors_list,
        "members": members,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "ordinary_string_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract source-free UGC upload HTTP-client configuration relationships from app.asar."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--anchor", action="append", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input, args.offset, anchors=args.anchor or DEFAULT_ANCHORS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V8 upload-config report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
