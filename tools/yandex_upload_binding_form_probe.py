"""Strict source-free V14 probe for Xc/RG binding forms in module 70204.

The probe emits only export/local identifiers, object-destructure property names,
parameter positions, expression shape labels, and allowlisted upload anchors.
It never extracts identifiers from string-bearing RHS expressions, so ordinary
string values cannot be promoted into the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yandex_upload_config_binding_probe as config_probe
import yandex_upload_contract_probe as contract_probe
import yandex_upload_export_alias_probe as alias_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


DEFAULT_PROVIDER_MODULE = "70204"
DEFAULT_EXPORTS = ("Xc", "RG")
ROLE_ANCHORS = (
    "UgcUploadHttpClient",
    "BaseResourceHttpClient",
    "ResourceHttpClient",
    "loader/upload-url",
    "getUploadUrl",
    "uploadFile",
    "createHttpOptions",
    "prefixUrl",
    "excludeHeaders",
    "withoutHeaders",
)
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,80}$")
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature|sign$)",
    re.IGNORECASE,
)
_OBJECT_BINDING_RE = re.compile(r"(?P<prefix>\b(?:const|let|var)\s+)?\{(?P<body>[^{}]{1,1600})\}\s*=\s*")
_ARRAY_BINDING_RE = re.compile(r"(?P<prefix>\b(?:const|let|var)\s+)?\[(?P<body>[^\[\]]{1,1200})\]\s*=\s*")
_FUNCTION_PARAMS_RE = re.compile(
    r"(?:\bfunction(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?\s*|(?<![A-Za-z0-9_$]))\((?P<body>[^()]{0,1600})\)\s*(?:=>|\{)"
)


def _safe_identifier(value: str) -> str | None:
    value = value.strip()
    if not _SAFE_IDENTIFIER_RE.fullmatch(value) or _SENSITIVE_RE.search(value):
        return None
    return value


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def _expression_end(body: str, start: int, *, max_chars: int = 4000) -> int:
    paren = bracket = brace = 0
    quote: str | None = None
    escaped = False
    limit = min(len(body), start + max_chars)
    i = start
    while i < limit:
        ch = body[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'", "`"}:
            quote = ch
        elif ch == "(":
            paren += 1
        elif ch == ")" and paren:
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]" and bracket:
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}" and brace:
            brace -= 1
        elif ch in {",", ";"} and paren == bracket == brace == 0:
            return i
        i += 1
    return limit


def _expression_shape(value: str) -> str:
    text = value.lstrip()
    if text.startswith("new "):
        return "new-expression"
    if text.startswith("{"):
        return "object-expression"
    if text.startswith("["):
        return "array-expression"
    if text.startswith("class"):
        return "class-expression"
    if text.startswith("function"):
        return "function-expression"
    if re.match(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\s*\(", text):
        return "call-expression"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", text):
        return "identifier-reference"
    if "=>" in text[:240]:
        return "arrow-expression"
    return "other-expression"


def _strip_default(value: str) -> str:
    candidate = value.strip()
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(candidate):
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
        elif char in "([{":
            depth += 1
        elif char in ")]}" and depth:
            depth -= 1
        elif char == "=" and depth == 0:
            return candidate[:index].strip()
    return candidate


def _object_bindings(body: str, targets: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in _OBJECT_BINDING_RE.finditer(body):
        pairs: list[dict[str, str]] = []
        for part in contract_probe._split_top_level(match.group("body")):  # noqa: SLF001
            colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
            if colon is None:
                local = _safe_identifier(_strip_default(part))
                prop = local
            else:
                prop = _safe_identifier(part[:colon].strip())
                local = _safe_identifier(_strip_default(part[colon + 1 :]))
            if local in targets and prop:
                pairs.append({"property": prop, "local": local})
        if not pairs:
            continue
        end = _expression_end(body, match.end())
        rhs = body[match.end():end]
        results.append(
            {
                "kind": "object-destructure",
                "pairs": pairs,
                "rhs_shape": _expression_shape(rhs),
                "rhs_anchors": [anchor for anchor in ROLE_ANCHORS if anchor in rhs],
            }
        )
    return results[:80]


def _array_bindings(body: str, targets: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in _ARRAY_BINDING_RE.finditer(body):
        locals_found: list[dict[str, Any]] = []
        for index, part in enumerate(contract_probe._split_top_level(match.group("body"))):  # noqa: SLF001
            local = _safe_identifier(_strip_default(part))
            if local in targets:
                locals_found.append({"index": index, "local": local})
        if not locals_found:
            continue
        end = _expression_end(body, match.end())
        rhs = body[match.end():end]
        results.append(
            {
                "kind": "array-destructure",
                "locals": locals_found,
                "rhs_shape": _expression_shape(rhs),
                "rhs_anchors": [anchor for anchor in ROLE_ANCHORS if anchor in rhs],
            }
        )
    return results[:80]


def _parameter_bindings(body: str, targets: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for match in _FUNCTION_PARAMS_RE.finditer(body):
        params = contract_probe._split_top_level(match.group("body"))  # noqa: SLF001
        found: list[dict[str, Any]] = []
        for index, part in enumerate(params):
            plain = _safe_identifier(_strip_default(part))
            if plain in targets:
                found.append({"index": index, "local": plain, "shape": "plain"})
                continue
            stripped = part.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                inner = stripped[1:-1]
                for item in contract_probe._split_top_level(inner):  # noqa: SLF001
                    colon = config_probe._find_top_level_colon(item)  # noqa: SLF001
                    if colon is None:
                        prop = local = _safe_identifier(_strip_default(item))
                    else:
                        prop = _safe_identifier(item[:colon].strip())
                        local = _safe_identifier(_strip_default(item[colon + 1 :]))
                    if local in targets and prop:
                        found.append(
                            {
                                "index": index,
                                "local": local,
                                "shape": "object-destructure",
                                "property": prop,
                            }
                        )
        if found:
            results.append({"kind": "function-parameters", "bindings": found})
    return results[:120]


def _provider_record(member_path: str, body: str, export_names: Iterable[str]) -> dict[str, Any]:
    exports = alias_probe._all_named_exports(body)  # noqa: SLF001
    by_name = {item["export_name"]: item["symbol"] for item in exports}
    targets: set[str] = set()
    export_symbols: list[dict[str, str]] = []
    for name in export_names:
        symbol = by_name.get(name)
        if not symbol:
            continue
        root = _safe_identifier(symbol.split(".")[-1])
        if not root:
            continue
        targets.add(root)
        export_symbols.append({"export_name": name, "symbol": symbol, "root": root})

    return {
        "member_path": member_path,
        "module_id": DEFAULT_PROVIDER_MODULE,
        "export_symbols": export_symbols,
        "object_destructures": _object_bindings(body, targets),
        "array_destructures": _array_bindings(body, targets),
        "parameter_bindings": _parameter_bindings(body, targets),
    }


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    provider_module_id: str = DEFAULT_PROVIDER_MODULE,
    export_names: Iterable[str] = DEFAULT_EXPORTS,
) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    data_start, mappings = target_probe.locate_members(path, offsets_list)
    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(key, {**member, "triggering_offsets": []})
            item["triggering_offsets"].append(mapping["offset"])

    member_summaries: list[dict[str, Any]] = []
    providers: list[dict[str, Any]] = []
    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        modules = wiring_probe._extract_modules(text)  # noqa: SLF001
        member_summaries.append(
            {
                "path": member["path"],
                "size": member["size"],
                "absolute_start": member["absolute_start"],
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "webpack_modules_detected": len(modules),
            }
        )
        for module in modules:
            if module["module_id"] != provider_module_id:
                continue
            record = _provider_record(member["path"], module["body"], export_names)
            record["module_id"] = provider_module_id
            providers.append(record)

    return {
        "format": "musicark-yandex-upload-binding-form-report-v1",
        "source": "asar-targeted-binding-form-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "provider_module_id": provider_module_id,
        "export_names": list(export_names),
        "members": member_summaries,
        "providers": providers,
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
    parser = argparse.ArgumentParser(description="Resolve Xc/RG binding forms without source or RHS string output.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--provider-module", default=DEFAULT_PROVIDER_MODULE)
    parser.add_argument("--export", action="append", dest="exports", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(
        args.input,
        args.offset,
        provider_module_id=str(args.provider_module),
        export_names=args.exports or DEFAULT_EXPORTS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V14 binding-form report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
