"""Contract-shape probe for Yandex Music UGC upload research.

The tool reads only selected ASAR members and emits structural relationships:
function parameter names, named invocation argument shapes, HTTP targets,
request option keys, search-parameter/header names, and simple member access.
It never emits raw JavaScript source, ordinary string values, credentials,
cookies, authorization values, or audio contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yandex_upload_target_probe as target_probe


DEFAULT_NAMES = ("getUploadUrl", "uploadFile", "runUpload")
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|sign(?:ature)?|credential)",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_MEMBER_RE = re.compile(
    r"^(?:[A-Za-z_$][A-Za-z0-9_$]*)(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$"
)
_HTTP_CALL_RE = re.compile(
    r"(?:this\.)?httpClient\.(get|post|put|patch|delete)\s*\(",
    re.IGNORECASE,
)
_OBJECT_KEY_RE = re.compile(
    r'''(?:"([^"]{1,100})"|'([^']{1,100})'|([A-Za-z_$][A-Za-z0-9_$-]{0,99}))\s*:'''
)
_PROTOCOL_TERMS = ("upload", "playlist", "ugc", "track", "file", "retry", "multipart")


def _find_matching(text: str, start: int, open_char: str, close_char: str) -> int | None:
    """Find a matching delimiter while ignoring quoted string contents."""
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
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
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_top_level(text: str) -> list[str]:
    """Split a JavaScript argument/object fragment on top-level commas."""
    parts: list[str] = []
    start = 0
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
        if char == "," and not stack:
            parts.append(text[start:index].strip())
            start = index + 1

    parts.append(text[start:].strip())
    return [part for part in parts if part]


def _unquote(value: str) -> str | None:
    if len(value) >= 2 and value[0] in {'"', "'", "`"} and value[-1] == value[0]:
        return value[1:-1]
    return None


def _safe_key(value: str) -> str | None:
    if not value or len(value) > 100 or _SENSITIVE_RE.search(value):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value) else None


def _object_keys(fragment: str) -> list[str]:
    keys: list[str] = []
    for match in _OBJECT_KEY_RE.finditer(fragment):
        raw = next(group for group in match.groups() if group is not None)
        key = _safe_key(raw)
        if key and key not in keys:
            keys.append(key)
    return keys[:120]


def _nested_keys(fragment: str, container: str) -> list[str]:
    match = re.search(rf"\b{re.escape(container)}\s*:\s*\{{", fragment)
    if match is None:
        return []
    start = fragment.find("{", match.start())
    end = _find_matching(fragment, start, "{", "}")
    if end is None:
        return []
    return _object_keys(fragment[start : end + 1])


def _classify_expression(expression: str) -> dict[str, Any]:
    value = expression.strip()
    literal = _unquote(value)
    if literal is not None:
        safe = target_probe._safe_protocol_literal(literal)  # noqa: SLF001
        return {"kind": "literal", "value": safe or "<string>"}
    if _IDENTIFIER_RE.fullmatch(value):
        return {"kind": "identifier", "value": value}
    if _MEMBER_RE.fullmatch(value):
        return {"kind": "member", "value": value}
    if value.startswith("{") and value.endswith("}"):
        return {"kind": "object", "keys": _object_keys(value)}
    if re.search(r"\bFormData\s*\(", value):
        return {"kind": "formdata"}
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return {"kind": "number"}
    return {"kind": "expression"}


def extract_http_contracts(text: str) -> list[dict[str, Any]]:
    """Extract direct httpClient call contracts without preserving source text."""
    contracts: list[dict[str, Any]] = []
    for match in _HTTP_CALL_RE.finditer(text):
        open_pos = text.find("(", match.start())
        end = _find_matching(text, open_pos, "(", ")")
        if end is None:
            continue
        args = _split_top_level(text[open_pos + 1 : end])
        if not args:
            continue

        contract: dict[str, Any] = {
            "method": match.group(1).upper(),
            "target": _classify_expression(args[0]),
        }
        if len(args) > 1:
            options = args[1].strip()
            if options.startswith("{") and options.endswith("}"):
                contract["option_keys"] = _object_keys(options)
                search_keys = _nested_keys(options, "searchParams")
                header_keys = _nested_keys(options, "headers")
                if search_keys:
                    contract["searchParams_keys"] = search_keys
                if header_keys:
                    contract["headers_keys"] = header_keys
                contract["has_body"] = bool(re.search(r"\bbody\s*:", options))
                contract["has_json"] = bool(re.search(r"\bjson\s*:", options))
                contract["has_signal"] = bool(re.search(r"\bsignal\s*:", options))
            else:
                contract["options"] = _classify_expression(options)
        if contract not in contracts:
            contracts.append(contract)
    return contracts[:120]


def extract_function_signatures(text: str, names: Iterable[str]) -> list[dict[str, Any]]:
    """Extract safe parameter-name shapes for selected methods/functions."""
    signatures: list[dict[str, Any]] = []
    for name in dict.fromkeys(names):
        patterns = (
            re.compile(rf"\b{re.escape(name)}\s*\(([^()]*)\)\s*\{{"),
            re.compile(rf"\b{re.escape(name)}\s*[:=]\s*(?:async\s*)?\(([^()]*)\)\s*=>"),
            re.compile(
                rf"\b{re.escape(name)}\s*[:=]\s*(?:async\s*)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=>"
            ),
        )
        for pattern in patterns:
            for match in pattern.finditer(text):
                params: list[str] = []
                for part in _split_top_level(match.group(1)):
                    clean = part.split("=", 1)[0].strip()
                    if _IDENTIFIER_RE.fullmatch(clean) and not _SENSITIVE_RE.search(clean):
                        params.append(clean)
                    else:
                        params.append("<pattern>")
                item = {"name": name, "params": params}
                if item not in signatures:
                    signatures.append(item)
    return signatures[:80]


def extract_named_invocations(text: str, names: Iterable[str]) -> list[dict[str, Any]]:
    """Extract argument shapes for calls to selected upload-related names."""
    invocations: list[dict[str, Any]] = []
    for name in dict.fromkeys(names):
        pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
        for match in pattern.finditer(text):
            open_pos = text.find("(", match.start())
            end = _find_matching(text, open_pos, "(", ")")
            if end is None:
                continue
            args = _split_top_level(text[open_pos + 1 : end])
            item = {"name": name, "args": [_classify_expression(arg) for arg in args]}
            if item not in invocations:
                invocations.append(item)
    return invocations[:160]


def extract_member_accesses(text: str) -> list[str]:
    """Keep only upload-contract-relevant member-access shapes."""
    allowed = {
        "url",
        "uploadUrl",
        "playlistId",
        "playlistKind",
        "trackId",
        "trackIds",
        "status",
        "body",
        "json",
        "file",
        "retry",
        "retryCount",
        "signal",
    }
    accesses: list[str] = []
    for match in re.finditer(
        r"\b([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\.([A-Za-z_$][A-Za-z0-9_$]*)",
        text,
    ):
        member = match.group(2)
        value = f"{match.group(1)}.{member}"
        if member in allowed and not _SENSITIVE_RE.search(value) and value not in accesses:
            accesses.append(value)
    return accesses[:160]


def analyze_contract(text: str, *, names: Iterable[str] = DEFAULT_NAMES) -> dict[str, Any]:
    """Return the source-free contract shape for one selected ASAR member."""
    name_list = list(dict.fromkeys(names))
    return {
        "function_signatures": extract_function_signatures(text, name_list),
        "http_contracts": extract_http_contracts(text),
        "named_invocations": extract_named_invocations(text, name_list),
        "member_accesses": extract_member_accesses(text),
        "form_fields": sorted(
            set(re.findall(r"\.append\(\s*[\"']([A-Za-z0-9_.:-]{1,80})[\"']\s*,", text))
        ),
        "protocol_literals": sorted(
            {
                safe
                for literal in re.findall(r'''["'`]([^"'`]{1,200})["'`]''', text)
                if (safe := target_probe._safe_protocol_literal(literal)) is not None  # noqa: SLF001
            }
        )[:120],
    }


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    names: Iterable[str] = DEFAULT_NAMES,
) -> dict[str, Any]:
    """Build a contract-shape report for ASAR members selected by known offsets."""
    offsets_list = list(dict.fromkeys(int(offset) for offset in offsets))
    name_list = list(dict.fromkeys(str(name) for name in names if str(name)))
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
                "contract": analyze_contract(text, names=name_list),
            }
        )

    return {
        "format": "musicark-yandex-upload-contract-report-v1",
        "source": "asar-contract-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "names": name_list,
        "members": members,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "source_code_contexts_included": False,
            "ordinary_string_values_included": False,
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
    print(f"Wrote contract sanitized report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a source-free request/call contract from selected Yandex Music ASAR members."
    )
    parser.add_argument("input", type=Path, help="Path to the official Yandex Music app.asar.")
    parser.add_argument(
        "--offset",
        type=int,
        action="append",
        required=True,
        help="Absolute byte offset used to select an ASAR member. Repeat as needed.",
    )
    parser.add_argument(
        "--name",
        action="append",
        default=None,
        help="Upload-related function name to analyze. Repeat to override defaults.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report instead of stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input, args.offset, names=args.name or DEFAULT_NAMES)
    _write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
