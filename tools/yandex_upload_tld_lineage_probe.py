"""Trace the exact webpack lineage of getTldHost/TLD_MARK without source leakage.

This probe follows only stable webpack module/export relationships beginning at
``91953.getTldHost`` and ``91953.TLD_MARK``. It resolves re-exports and simple
local aliases until a concrete function/value definition is reached, then emits
only normalized operator/parameter structure and tightly allowlisted marker or
Yandex host-template literals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_contract_probe as contract_probe
import yandex_upload_export_alias_probe as export_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


START_MODULE_ID = "91953"
TARGET_EXPORTS = ("getTldHost", "TLD_MARK")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_SAFE_MEMBER_RE = re.compile(r"^(?P<base>[A-Za-z_$][A-Za-z0-9_$]{0,100})\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{0,100})$")
_SAFE_MARKER_RE = re.compile(r"^[A-Za-z0-9_.{}:$%+-]{1,40}$")
_SAFE_TEMPLATE_RE = re.compile(r"^https?://[A-Za-z0-9._:{}$%+-]*yandex[A-Za-z0-9._:{}$%+-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+-]*)?$", re.IGNORECASE)
_SENSITIVE_RE = re.compile(r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)", re.IGNORECASE)


def _hash(module_id: str, value: str) -> str:
    return dataflow_probe._alias(module_id, value)  # noqa: SLF001


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _exports(body: str) -> dict[str, str]:
    return {item["export_name"]: item["symbol"] for item in export_probe._all_named_exports(body)}  # noqa: SLF001


def _assignment(body: str, symbol: str) -> str | None:
    if not _SAFE_IDENTIFIER_RE.fullmatch(symbol):
        return None
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?!=|>)")
    for match in pattern.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return rhs.strip()
    return None


def _import_target(body: str, expression: str) -> tuple[str, str] | None:
    match = _SAFE_MEMBER_RE.fullmatch(expression.strip())
    if not match:
        return None
    base, member = match.group("base"), match.group("member")
    for item in wiring_probe._imports(body):  # noqa: SLF001
        if item["local"] == base:
            return item["source_module_id"], member
    return None


def _safe_literal(value: str) -> str | None:
    clean = value.strip()
    if not clean or _SENSITIVE_RE.search(clean) or "?" in clean or "#" in clean:
        return None
    if _SAFE_TEMPLATE_RE.fullmatch(clean):
        return clean
    if _SAFE_MARKER_RE.fullmatch(clean) and ("tld" in clean.lower() or "{" in clean or "%" in clean or "$" in clean):
        return clean
    return None


def _safe_literals(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        safe = _safe_literal(value)
        if safe and safe not in results:
            results.append(safe)
    return results[:20]


def _function_definition(module_id: str, body: str, symbol: str) -> dict[str, Any] | None:
    if not _SAFE_IDENTIFIER_RE.fullmatch(symbol):
        return None
    imports = wiring_probe._imports(body)  # noqa: SLF001
    patterns = (
        re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\((?P<params>[^()]*)\)\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*function(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?\s*\((?P<params>[^()]*)\)\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*\((?P<params>[^()]*)\)\s*=>\s*\{{"),
    )
    for pattern in patterns:
        match = pattern.search(body)
        if not match:
            continue
        brace = body.find("{", match.start(), match.end())
        end = contract_probe._find_matching(body, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        params = [item.strip() for item in contract_probe._split_top_level(match.group("params")) if item.strip()]  # noqa: SLF001
        fragment = body[brace + 1 : end]
        returns: list[list[str]] = []
        literals: list[str] = []
        for return_match in re.finditer(r"\breturn\b", fragment):
            expression = prefix_probe._slice_rhs(fragment, return_match.end())  # noqa: SLF001
            if not expression:
                continue
            normalized = prefix_probe._normalized_expression(module_id, expression, imports)  # noqa: SLF001
            replacements = {_hash(module_id, param): f"param:{index}" for index, param in enumerate(params)}
            normalized = [replacements.get(token, token) for token in normalized]
            if normalized not in returns:
                returns.append(normalized)
            for literal in _safe_literals(expression):
                if literal not in literals:
                    literals.append(literal)
        return {
            "definition": "function",
            "parameterCount": len(params),
            "normalizedReturns": returns[:12],
            "safeLiterals": literals[:20],
        }

    arrow = re.search(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?:\((?P<params>[^()]*)\)|(?P<param>[A-Za-z_$][A-Za-z0-9_$]*))\s*=>\s*", body)
    if arrow and (arrow.end() >= len(body) or body[arrow.end()] != "{"):
        params_text = arrow.groupdict().get("params")
        params = [item.strip() for item in contract_probe._split_top_level(params_text) if item.strip()] if params_text is not None else [arrow.group("param")]  # noqa: SLF001
        expression = prefix_probe._slice_rhs(body, arrow.end())  # noqa: SLF001
        if expression:
            normalized = prefix_probe._normalized_expression(module_id, expression, imports)  # noqa: SLF001
            replacements = {_hash(module_id, param): f"param:{index}" for index, param in enumerate(params)}
            return {
                "definition": "function",
                "parameterCount": len(params),
                "normalizedReturns": [[replacements.get(token, token) for token in normalized]],
                "safeLiterals": _safe_literals(expression),
            }
    return None


def _resolve_export(index: dict[str, list[dict[str, Any]]], module_id: str, export_key: str, *, max_depth: int = 8) -> dict[str, Any]:
    current_module, current_export = module_id, export_key
    visited: set[tuple[str, str]] = set()
    lineage: list[dict[str, str]] = []
    for _ in range(max_depth + 1):
        state = (current_module, current_export)
        if state in visited:
            return {"lineage": lineage, "terminal": {"kind": "cycle", "module_id": current_module, "export_key": current_export}}
        visited.add(state)
        candidates = index.get(current_module) or []
        if not candidates:
            return {"lineage": lineage, "terminal": {"kind": "module-missing", "module_id": current_module, "export_key": current_export}}
        body = candidates[0]["body"]
        symbol = _exports(body).get(current_export)
        if not symbol:
            return {"lineage": lineage, "terminal": {"kind": "export-missing", "module_id": current_module, "export_key": current_export}}

        direct = _import_target(body, symbol)
        if direct:
            next_module, next_export = direct
            lineage.append({"from_module_id": current_module, "from_export_key": current_export, "to_module_id": next_module, "to_export_key": next_export})
            current_module, current_export = next_module, next_export
            continue

        local = symbol.split(".")[-1]
        function = _function_definition(current_module, body, local)
        if function:
            return {"lineage": lineage, "terminal": {"kind": "function", "module_id": current_module, "export_key": current_export, **function}}

        rhs = _assignment(body, local)
        if rhs:
            imported = _import_target(body, rhs)
            if imported:
                next_module, next_export = imported
                lineage.append({"from_module_id": current_module, "from_export_key": current_export, "to_module_id": next_module, "to_export_key": next_export})
                current_module, current_export = next_module, next_export
                continue
            if _SAFE_IDENTIFIER_RE.fullmatch(rhs):
                alias_function = _function_definition(current_module, body, rhs)
                if alias_function:
                    return {"lineage": lineage, "terminal": {"kind": "function", "module_id": current_module, "export_key": current_export, **alias_function}}
                alias_rhs = _assignment(body, rhs)
                if alias_rhs:
                    imported = _import_target(body, alias_rhs)
                    if imported:
                        next_module, next_export = imported
                        lineage.append({"from_module_id": current_module, "from_export_key": current_export, "to_module_id": next_module, "to_export_key": next_export})
                        current_module, current_export = next_module, next_export
                        continue
            safe_literals = _safe_literals(rhs)
            return {
                "lineage": lineage,
                "terminal": {
                    "kind": "value",
                    "module_id": current_module,
                    "export_key": current_export,
                    "valueShape": prefix_probe._normalized_expression(current_module, rhs, wiring_probe._imports(body)),  # noqa: SLF001
                    "safeLiterals": safe_literals,
                },
            }
        return {"lineage": lineage, "terminal": {"kind": "unresolved", "module_id": current_module, "export_key": current_export}}
    return {"lineage": lineage, "terminal": {"kind": "max-depth", "module_id": current_module, "export_key": current_export}}


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    index: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            index.setdefault(module["module_id"], []).append({
                "member_path": entry["path"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "body": module["body"],
            })

    results = {export: _resolve_export(index, START_MODULE_ID, export) for export in TARGET_EXPORTS}
    return {
        "format": "musicark-yandex-upload-tld-lineage-v1",
        "source": "asar-webpack-tld-export-lineage",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "start_module_id": START_MODULE_ID,
        "exports": results,
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
    parser = argparse.ArgumentParser(description="Trace getTldHost/TLD_MARK webpack lineage safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized TLD lineage report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
