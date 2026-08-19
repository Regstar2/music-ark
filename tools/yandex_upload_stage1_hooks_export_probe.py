"""Resolve the exact ``73202.hooks`` value feeding the stage-one prefix.

V40 proved that the first argument of the stage-one ``getTldHost`` call is a
minified local whose nearest assignment is webpack module 73202 export
``hooks``. This probe follows only that one stable export to its local
definition and emits structural tokens plus allowlisted public Yandex URL
templates. Raw identifiers, arbitrary strings and source contexts are omitted.
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


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _export_symbol(body: str) -> str | None:
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
            if colon is None:
                continue
            key = part[:colon].strip().strip("\"'")
            if key != EXPORT_KEY:
                continue
            symbol = wiring_probe._export_symbol(part[colon + 1 :])  # noqa: SLF001
            if symbol and _IDENTIFIER_RE.fullmatch(symbol):
                return symbol
    return None


def _nearest_definition(body: str, symbol: str, before: int | None = None) -> tuple[int, str] | None:
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


def _trace_symbol(body: str, symbol: str, imports: list[dict[str, str]], *, max_depth: int = 6) -> list[dict[str, Any]]:
    current = symbol
    before: int | None = None
    seen: set[str] = set()
    chain: list[dict[str, Any]] = []
    for depth in range(max_depth + 1):
        record: dict[str, Any] = {
            "depth": depth,
            "kind": "identifier" if _IDENTIFIER_RE.fullmatch(current) else "expression",
            "sourceRefs": _import_refs(current, imports),
            "safeYandexTemplates": use_site_probe._safe_literals(current),  # noqa: SLF001
            "normalized": prefix_probe._normalized_expression(MODULE_ID, current, imports),  # noqa: SLF001
        }
        if _IDENTIFIER_RE.fullmatch(current):
            record["aliasHash"] = dataflow_probe._alias(MODULE_ID, current)  # noqa: SLF001
        chain.append(record)
        if not _IDENTIFIER_RE.fullmatch(current) or current in seen:
            break
        seen.add(current)
        assigned = _nearest_definition(body, current, before)
        if not assigned:
            break
        before, current = assigned
    return chain


def analyze_body(body: str) -> dict[str, Any]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    symbol = _export_symbol(body)
    if not symbol:
        return {"exportFound": False}
    return {
        "exportFound": True,
        "exportKey": EXPORT_KEY,
        "localSymbolHash": dataflow_probe._alias(MODULE_ID, symbol),  # noqa: SLF001
        "chain": _trace_symbol(body, symbol, imports),
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
            if module["module_id"] != MODULE_ID:
                continue
            analysis = analyze_body(module["body"])
            if analysis.get("exportFound"):
                matches.append(
                    {
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        "module_id": MODULE_ID,
                        "analysis": analysis,
                    }
                )
    return {
        "format": "musicark-yandex-upload-stage1-hooks-export-v1",
        "source": "asar-stage1-hooks-export-definition-trace",
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
    parser = argparse.ArgumentParser(description="Resolve the exact stage-one hooks export safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one hooks export report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
