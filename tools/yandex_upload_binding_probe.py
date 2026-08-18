"""Source-free binding probe for the Yandex Music UGC upload contract.

V6 narrows the already identified upload API member to the bodies of selected
functions and emits only structural bindings: function parameters, parameter
member accesses, HTTP call shapes and object-key -> expression relationships.
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

import yandex_upload_contract_probe as contract_probe
import yandex_upload_target_probe as target_probe


DEFAULT_NAMES = ("getUploadUrl", "uploadFile")
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|(?:^|[._:-])sign(?:ature)?(?:$|[._:-]))",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_MEMBER_RE = re.compile(
    r"^(?:[A-Za-z_$][A-Za-z0-9_$]*)(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+$"
)
_KEY_RE = re.compile(r"^(?:[A-Za-z_$][A-Za-z0-9_$-]*|[\"'][^\"']+[\"'])$")


def _safe_name(value: str) -> str | None:
    clean = value.strip().strip("\"'")
    if not clean or len(clean) > 100 or _SENSITIVE_RE.search(clean):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", clean):
        return None
    return clean


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


def _classify_binding_expression(value: str) -> dict[str, Any]:
    expression = value.strip()
    if _IDENTIFIER_RE.fullmatch(expression) and not _SENSITIVE_RE.search(expression):
        return {"kind": "identifier", "value": expression}
    if _MEMBER_RE.fullmatch(expression) and not _SENSITIVE_RE.search(expression):
        return {"kind": "member", "value": expression}
    if re.fullmatch(r"\d+(?:\.\d+)?", expression):
        return {"kind": "number"}
    if expression in {"true", "false"}:
        return {"kind": "boolean"}
    if expression == "null":
        return {"kind": "null"}
    if expression.startswith("{") and expression.endswith("}"):
        return {"kind": "object"}
    if re.search(r"\bFormData\b", expression):
        return {"kind": "formdata"}
    return {"kind": "expression"}


def _parse_object_bindings(fragment: str, *, prefix: str = "") -> list[dict[str, Any]]:
    """Parse simple nested object-literal key bindings without preserving values."""
    value = fragment.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return []
    inner = value[1:-1]
    results: list[dict[str, Any]] = []
    for part in contract_probe._split_top_level(inner):  # noqa: SLF001
        if part.startswith("..."):
            spread = part[3:].strip()
            if (_IDENTIFIER_RE.fullmatch(spread) or _MEMBER_RE.fullmatch(spread)) and not _SENSITIVE_RE.search(spread):
                results.append(
                    {
                        "path": f"{prefix}..." if prefix else "...",
                        "value": {"kind": "spread", "value": spread},
                    }
                )
            continue
        colon = _find_top_level_colon(part)
        if colon is None:
            continue
        raw_key = part[:colon].strip()
        rhs = part[colon + 1 :].strip()
        if not _KEY_RE.fullmatch(raw_key):
            continue
        key = _safe_name(raw_key)
        if key is None:
            continue
        path = f"{prefix}.{key}" if prefix else key
        classified = _classify_binding_expression(rhs)
        results.append({"path": path, "value": classified})
        if classified["kind"] == "object":
            results.extend(_parse_object_bindings(rhs, prefix=path))
    return results


def _all_object_bindings(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        end = contract_probe._find_matching(text, index, "{", "}")  # noqa: SLF001
        if end is None:
            continue
        for item in _parse_object_bindings(text[index : end + 1]):
            if item not in results:
                results.append(item)
    return results[:240]


def _parameter_member_accesses(body: str, params: Iterable[str]) -> list[str]:
    results: list[str] = []
    for param in params:
        if not _IDENTIFIER_RE.fullmatch(param) or _SENSITIVE_RE.search(param):
            continue
        pattern = re.compile(
            rf"\b{re.escape(param)}((?:\.[A-Za-z_$][A-Za-z0-9_$]*)+)"
        )
        for match in pattern.finditer(body):
            value = param + match.group(1)
            if _SENSITIVE_RE.search(value) or value in results:
                continue
            results.append(value)
    return results[:160]


def extract_function_bodies(text: str, names: Iterable[str]) -> list[dict[str, Any]]:
    """Extract source-free structure from selected function/method bodies."""
    results: list[dict[str, Any]] = []
    for name in dict.fromkeys(names):
        patterns = (
            re.compile(rf"\b{re.escape(name)}\s*\(([^()]*)\)\s*\{{"),
            re.compile(rf"\b{re.escape(name)}\s*[:=]\s*(?:async\s*)?\(([^()]*)\)\s*=>\s*\{{"),
            re.compile(
                rf"\b{re.escape(name)}\s*[:=]\s*(?:async\s*)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*\{{"
            ),
        )
        seen_starts: set[int] = set()
        for pattern in patterns:
            for match in pattern.finditer(text):
                brace = text.find("{", match.end() - 1)
                if brace < 0 or brace in seen_starts:
                    continue
                end = contract_probe._find_matching(text, brace, "{", "}")  # noqa: SLF001
                if end is None:
                    continue
                seen_starts.add(brace)
                params: list[str] = []
                for part in contract_probe._split_top_level(match.group(1)):  # noqa: SLF001
                    clean = part.split("=", 1)[0].strip()
                    params.append(clean if _IDENTIFIER_RE.fullmatch(clean) and not _SENSITIVE_RE.search(clean) else "<pattern>")
                body = text[brace + 1 : end]
                item = {
                    "name": name,
                    "params": params,
                    "parameter_member_accesses": _parameter_member_accesses(body, params),
                    "http_contracts": contract_probe.extract_http_contracts(body),
                    "named_invocations": contract_probe.extract_named_invocations(body, DEFAULT_NAMES),
                    "object_bindings": _all_object_bindings(body),
                    "form_fields": sorted(
                        set(re.findall(r"\.append\(\s*[\"']([A-Za-z0-9_.:-]{1,80})[\"']\s*,", body))
                    ),
                }
                if item not in results:
                    results.append(item)
    return results[:40]


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def build_report(path: Path, offsets: Iterable[int], *, names: Iterable[str] = DEFAULT_NAMES) -> dict[str, Any]:
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
                "functions": extract_function_bodies(text, name_list),
            }
        )

    return {
        "format": "musicark-yandex-upload-binding-report-v1",
        "source": "asar-function-binding-static-scan",
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
    print(f"Wrote binding sanitized report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract source-free parameter/object bindings from selected Yandex upload functions."
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
        help="Function name to analyze. Repeat to override defaults.",
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
