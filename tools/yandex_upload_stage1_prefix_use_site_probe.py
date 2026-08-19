"""Trace the exact stage-one prefix arguments at their use site.

This probe resolves the ``prefixUrl`` expression passed to ``new 12690.S`` in
composition module 7644, then walks the nearest preceding assignment for each
``getTldHost`` argument. This avoids treating a minified local's original
webpack import binding as its value when that local was reassigned later.

Only hashed locals, stable webpack module/export refs, structural tokens and
allowlisted public Yandex URL templates are emitted. Raw JavaScript, arbitrary
strings, credentials, headers and query values are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
STAGE1_MODULE_ID = "12690"
HELPER_MODULE_ID = "91953"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_SAFE_TEMPLATE_RE = re.compile(
    r"^https?://[A-Za-z0-9._:{}$%+\-]*yandex[A-Za-z0-9._:{}$%+\-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+\-]*)?$",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|credential|password|signature)",
    re.IGNORECASE,
)


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _hash(value: str) -> str:
    return dataflow_probe._alias(COMPOSITION_MODULE_ID, value)  # noqa: SLF001


def _safe_literals(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'\"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        clean = value.strip()
        if (
            clean
            and "?" not in clean
            and "#" not in clean
            and not _SENSITIVE_RE.search(clean)
            and _SAFE_TEMPLATE_RE.fullmatch(clean)
            and clean not in results
        ):
            results.append(clean)
    return results[:20]


def _import_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(
            rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})"
        )
        members = list(member_pattern.finditer(expression))
        for match in members:
            record = {"source_module_id": item["source_module_id"], "export_key": match.group("member")}
            if record not in results:
                results.append(record)
        if not members and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _constructor_prefix(body: str) -> tuple[int, str, list[dict[str, str]]] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    for item in imports:
        if item["source_module_id"] != STAGE1_MODULE_ID:
            continue
        pattern = re.compile(rf"\bnew\s+{re.escape(item['local'])}\.S\s*\(")
        for match in pattern.finditer(body):
            open_paren = body.find("(", match.start(), match.end())
            end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
            if end is None:
                continue
            args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
            for arg in args:
                prefix = prefix_probe._object_property_rhs(arg, "prefixUrl")  # noqa: SLF001
                if prefix is None:
                    continue
                position = body.find(prefix, open_paren, end)
                return (position if position >= 0 else match.start(), prefix, imports)
    return None


def _get_tld_host_call(expression: str, imports: list[dict[str, str]]) -> tuple[int, list[str]] | None:
    for item in imports:
        if item["source_module_id"] != HELPER_MODULE_ID:
            continue
        marker = re.search(rf"\b{re.escape(item['local'])}\.getTldHost\b", expression)
        if not marker:
            continue
        open_paren = expression.find("(", marker.end())
        if open_paren < 0:
            continue
        end = contract_probe._find_matching(expression, open_paren, "(", ")")  # noqa: SLF001
        if end is None:
            continue
        args = [part.strip() for part in contract_probe._split_top_level(expression[open_paren + 1 : end])]  # noqa: SLF001
        if len(args) == 3:
            return marker.start(), args
    return None


def _nearest_assignment(body: str, identifier: str, before: int) -> tuple[int, str] | None:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        return None
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)"
    )
    matches = [match for match in pattern.finditer(body, 0, max(0, before))]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return match.start(), rhs.strip()
    return None


def _trace(body: str, expression: str, before: int, imports: list[dict[str, str]], *, max_depth: int = 8) -> list[dict[str, Any]]:
    current = expression.strip()
    cursor = before
    seen: set[str] = set()
    chain: list[dict[str, Any]] = []
    for depth in range(max_depth + 1):
        record: dict[str, Any] = {
            "depth": depth,
            "kind": "identifier" if _IDENTIFIER_RE.fullmatch(current) else "expression",
            "sourceRefs": _import_refs(current, imports),
            "safeYandexTemplates": _safe_literals(current),
            "normalized": prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, current, imports),  # noqa: SLF001
        }
        if _IDENTIFIER_RE.fullmatch(current):
            record["aliasHash"] = _hash(current)
        chain.append(record)
        if not _IDENTIFIER_RE.fullmatch(current) or current in seen:
            break
        seen.add(current)
        assigned = _nearest_assignment(body, current, cursor)
        if not assigned:
            break
        cursor, current = assigned
    return chain


def analyze_body(body: str) -> dict[str, Any]:
    found = _constructor_prefix(body)
    if not found:
        return {"stage1PrefixFound": False}
    prefix_pos, prefix_expression, imports = found
    helper = _get_tld_host_call(prefix_expression, imports)
    if not helper:
        return {
            "stage1PrefixFound": True,
            "getTldHostCallFound": False,
            "normalizedPrefix": prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, prefix_expression, imports),  # noqa: SLF001
        }
    _, arguments = helper
    return {
        "stage1PrefixFound": True,
        "getTldHostCallFound": True,
        "argumentCount": len(arguments),
        "arguments": [
            {"index": index, "chain": _trace(body, argument, prefix_pos, imports)}
            for index, argument in enumerate(arguments)
        ],
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    matches: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] != COMPOSITION_MODULE_ID:
                continue
            matches.append(
                {
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": COMPOSITION_MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                }
            )
    return {
        "format": "musicark-yandex-upload-stage1-prefix-use-site-v1",
        "source": "asar-exact-stage1-prefix-nearest-assignment-trace",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "matches": matches[:20],
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
    parser = argparse.ArgumentParser(description="Trace the exact stage-one prefix use site safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one prefix use-site report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
