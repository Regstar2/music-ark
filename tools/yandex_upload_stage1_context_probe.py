"""Trace stage-one constructor context and TLD origins at the exact use site.

The probe is limited to composition module 7644. It resolves the first argument
passed to ``new 12690.S`` and the value assigned to ``this.tld`` using nearest
use-site assignments. Output contains only stable webpack module/export refs,
semantic ``this`` property paths, hashed locals and allowlisted public TLD enum
values. No credential/header values, arbitrary strings or raw local names are
emitted.
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


MODULE_ID = "7644"
STAGE1_MODULE_ID = "12690"
_TLDS = {"ru", "com", "kz", "by", "uz", "tr", "am", "az", "ge", "kg", "md", "tj"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")


def _hash(value: str) -> str:
    return dataflow_probe._alias(MODULE_ID, value)  # noqa: SLF001


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _constructor_call(body: str) -> tuple[int, list[str], list[dict[str, str]]] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    for item in imports:
        if item["source_module_id"] != STAGE1_MODULE_ID:
            continue
        match = re.search(rf"\bnew\s+{re.escape(item['local'])}\.S\s*\(", body)
        if not match:
            continue
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = [part.strip() for part in contract_probe._split_top_level(body[open_paren + 1:end])]  # noqa: SLF001
        return match.start(), args, imports
    return None


def _import_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})")
        found_member = False
        for match in member_pattern.finditer(expression):
            record = {"source_module_id": item["source_module_id"], "export_key": match.group("member")}
            if record not in results:
                results.append(record)
            found_member = True
        if not found_member and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _semantic_this_path(expression: str) -> list[str] | None:
    clean = re.sub(r"\s+", "", expression).replace("?.", ".")
    match = re.fullmatch(r"this(?:\.[A-Za-z_$][A-Za-z0-9_$]{0,100}){1,5}", clean)
    return clean.split(".") if match else None


def _public_tlds(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        if value in _TLDS and value not in results:
            results.append(value)
    return results


def _nearest_assignment(body: str, identifier: str, before: int) -> tuple[int, str] | None:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        return None
    pattern = re.compile(rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)")
    matches = [m for m in pattern.finditer(body, 0, before)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return match.start(), rhs.strip()
    return None


def _trace_expression(body: str, expression: str, before: int, imports: list[dict[str, str]], *, max_depth: int = 5) -> dict[str, Any]:
    current = expression.strip()
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = before
    for depth in range(max_depth + 1):
        record: dict[str, Any] = {
            "depth": depth,
            "kind": "identifier" if _IDENTIFIER_RE.fullmatch(current) else "expression",
            "sourceRefs": _import_refs(current, imports),
            "semanticThisPath": _semantic_this_path(current),
            "publicTlds": _public_tlds(current),
            "normalized": prefix_probe._normalized_expression(MODULE_ID, current, imports),  # noqa: SLF001
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
    return {"chain": chain}


def _tld_assignment(body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    pattern = re.compile(r"\bthis\.tld\s*=\s*(?!=)")
    for match in pattern.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if not rhs:
            continue
        results.append({
            "sourceRefs": _import_refs(rhs, imports),
            "semanticThisPath": _semantic_this_path(rhs),
            "publicTlds": _public_tlds(rhs),
            "normalized": prefix_probe._normalized_expression(MODULE_ID, rhs, imports),  # noqa: SLF001
        })
    return results[:40]


def analyze_body(body: str) -> dict[str, Any]:
    found = _constructor_call(body)
    if not found:
        return {"stage1ConstructorFound": False}
    call_pos, args, imports = found
    return {
        "stage1ConstructorFound": True,
        "argumentCount": len(args),
        "argument0": _trace_expression(body, args[0], call_pos, imports) if args else None,
        "tldAssignments": _tld_assignment(body, imports),
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
            if module["module_id"] == MODULE_ID:
                matches.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-stage1-context-v1",
        "source": "asar-stage1-context-and-tld-use-site-lineage",
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
    parser = argparse.ArgumentParser(description="Trace stage-one HTTP context and TLD origins safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one context report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
