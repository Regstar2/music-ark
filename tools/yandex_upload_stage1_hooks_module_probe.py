"""Resolve module 73202 / export ``hooks`` across alternate webpack forms.

V40 proved that ``73202.hooks`` supplies the first argument of the exact
stage-one ``getTldHost`` call. The generic module parser did not extract module
73202, so this probe recognizes only this one module ID in quoted/unquoted
webpack object-key forms and only the stable ``hooks`` export via webpack ``.d``,
direct export assignment, or ``Object.defineProperty``.

Output is restricted to module/export structure, hashed local symbols, stable
module/member refs, and allowlisted public Yandex URL templates. It never emits
JavaScript source, arbitrary strings, credentials, header/query values, or raw
local identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_config_binding_probe as config_probe
import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_stage1_prefix_use_site_probe as use_site_probe
import yandex_upload_target_probe as target_probe


MODULE_ID = "73202"
EXPORT_KEY = "hooks"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_MODULE_START_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?:[\"'])?73202(?:[\"'])?\s*:\s*"
    r"(?:(?:function\s*\([^)]{0,240}\))|(?:\([^)]{0,240}\)\s*=>)|(?:[A-Za-z_$][A-Za-z0-9_$]*\s*=>))\s*\{"
)


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _extract_target_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    for match in _MODULE_START_RE.finditer(text):
        brace = text.find("{", match.start(), match.end())
        if brace < 0:
            continue
        end = contract_probe._find_matching(text, brace, "{", "}")  # noqa: SLF001
        if end is not None:
            bodies.append(text[brace + 1 : end])
    return bodies[:20]


def _getter_symbol(value: str) -> str | None:
    clean = value.strip()
    patterns = (
        re.compile(r"^(?:\(\)\s*=>|[A-Za-z_$][A-Za-z0-9_$]*\s*=>)\s*(?P<symbol>[A-Za-z_$][A-Za-z0-9_$]*)$"),
        re.compile(r"^function\s*\(\)\s*\{\s*return\s+(?P<symbol>[A-Za-z_$][A-Za-z0-9_$]*)\s*;?\s*\}$"),
    )
    for pattern in patterns:
        found = pattern.match(clean)
        if found:
            return found.group("symbol")
    return None


def _export_candidates(body: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    # webpack runtime: runtime.d(exports,{hooks:()=>local})
    for match in re.finditer(r"\b[A-Za-z_$][A-Za-z0-9_$]*\.d\s*\(", body):
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        if len(args) < 2:
            continue
        export_map = args[1].strip()
        if not (export_map.startswith("{") and export_map.endswith("}")):
            continue
        for part in contract_probe._split_top_level(export_map[1:-1]):  # noqa: SLF001
            colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
            if colon is None or part[:colon].strip().strip("\"'") != EXPORT_KEY:
                continue
            symbol = _getter_symbol(part[colon + 1 :])
            results.append({"form": "webpack-d", "symbol": symbol})

    # CommonJS-ish direct export: exports.hooks = local
    for match in re.finditer(r"\b[A-Za-z_$][A-Za-z0-9_$]*\.hooks\s*=\s*(?!=)", body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        symbol = rhs.strip() if rhs and _IDENTIFIER_RE.fullmatch(rhs.strip()) else None
        results.append({"form": "direct-assignment", "symbol": symbol})

    # Object.defineProperty(exports,"hooks",{get:()=>local})
    for match in re.finditer(r"\bObject\.defineProperty\s*\(", body):
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        if len(args) < 3 or args[1].strip().strip("\"'") != EXPORT_KEY:
            continue
        descriptor = args[2].strip()
        symbol = None
        if descriptor.startswith("{") and descriptor.endswith("}"):
            for part in contract_probe._split_top_level(descriptor[1:-1]):  # noqa: SLF001
                colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
                if colon is not None and part[:colon].strip().strip("\"'") == "get":
                    symbol = _getter_symbol(part[colon + 1 :])
        results.append({"form": "define-property", "symbol": symbol})

    unique: list[dict[str, Any]] = []
    for item in results:
        if item not in unique:
            unique.append(item)
    return unique[:20]


def _nearest_definition(body: str, symbol: str, before: int | None = None) -> tuple[int, str] | None:
    if not _IDENTIFIER_RE.fullmatch(symbol):
        return None
    limit = len(body) if before is None else max(0, before)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(symbol)}\s*=\s*(?!=|>)"
    )
    matches = [match for match in pattern.finditer(body, 0, limit)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return match.start(), rhs.strip()
    return None


def _source_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(
            rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})"
        )
        members = list(member_pattern.finditer(expression))
        for found in members:
            record = {"source_module_id": item["source_module_id"], "export_key": found.group("member")}
            if record not in results:
                results.append(record)
        if not members and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _trace(body: str, symbol: str, imports: list[dict[str, str]], *, max_depth: int = 8) -> list[dict[str, Any]]:
    current = symbol
    cursor: int | None = None
    seen: set[str] = set()
    chain: list[dict[str, Any]] = []
    for depth in range(max_depth + 1):
        record: dict[str, Any] = {
            "depth": depth,
            "kind": "identifier" if _IDENTIFIER_RE.fullmatch(current) else "expression",
            "sourceRefs": _source_refs(current, imports),
            "safeYandexTemplates": use_site_probe._safe_literals(current),  # noqa: SLF001
            "normalized": prefix_probe._normalized_expression(MODULE_ID, current, imports),  # noqa: SLF001
        }
        if _IDENTIFIER_RE.fullmatch(current):
            record["aliasHash"] = dataflow_probe._alias(MODULE_ID, current)  # noqa: SLF001
        chain.append(record)
        if not _IDENTIFIER_RE.fullmatch(current) or current in seen:
            break
        seen.add(current)
        assigned = _nearest_definition(body, current, cursor)
        if not assigned:
            break
        cursor, current = assigned
    return chain


def analyze_body(body: str) -> dict[str, Any]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    exports = _export_candidates(body)
    records: list[dict[str, Any]] = []
    for export in exports:
        symbol = export.get("symbol")
        record: dict[str, Any] = {"form": export["form"], "symbolResolved": bool(symbol)}
        if isinstance(symbol, str) and _IDENTIFIER_RE.fullmatch(symbol):
            record["localSymbolHash"] = dataflow_probe._alias(MODULE_ID, symbol)  # noqa: SLF001
            record["chain"] = _trace(body, symbol, imports)
        records.append(record)
    return {"hooksExportFound": bool(exports), "exports": records}


def build_report(path: Path, *, max_member_size: int = 16_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    occurrences: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        bodies = _extract_target_bodies(text)
        if not bodies:
            continue
        for body in bodies:
            occurrences.append(
                {
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "moduleForm": "quoted-or-unquoted-object-key",
                    "analysis": analyze_body(body),
                }
            )
    return {
        "format": "musicark-yandex-upload-stage1-hooks-module-v1",
        "source": "asar-targeted-alternate-webpack-hooks-module-trace",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "occurrences": occurrences[:20],
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
    parser = argparse.ArgumentParser(description="Resolve alternate webpack forms for stage-one module 73202 hooks.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized alternate hooks module report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
