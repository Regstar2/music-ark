"""Resolve the standard method used by getTldHost and classify its stage-one args.

Only the proven ``91953.getTldHost`` definition and its call in composition
module 7644 are inspected. Standard string methods are allowlisted explicitly;
arguments are reduced to stable webpack module/export provenance or structural
kinds. No arbitrary string or local identifier is emitted.
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
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_stage1_auth_lineage_probe as auth_probe
import yandex_upload_target_probe as target_probe


HELPER_MODULE_ID = "91953"
COMPOSITION_MODULE_ID = "7644"
_SAFE_METHODS = {"replace", "replaceAll"}


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _exports(body: str) -> dict[str, str]:
    return {item["export_name"]: item["symbol"] for item in export_probe._all_named_exports(body)}  # noqa: SLF001


def _get_tld_method(body: str) -> dict[str, Any]:
    symbol = (_exports(body).get("getTldHost") or "").split(".")[-1]
    if not symbol:
        return {"resolved": False}
    patterns = (
        re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\((?P<params>[^()]*)\)\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?:function\s*)?\((?P<params>[^()]*)\)\s*(?:=>)?\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*\((?P<params>[^()]*)\)\s*=>\s*"),
    )
    for pattern in patterns:
        match = pattern.search(body)
        if not match:
            continue
        params = [item.strip() for item in contract_probe._split_top_level(match.group("params")) if item.strip()]  # noqa: SLF001
        if len(params) < 3:
            continue
        if match.end() < len(body) and body[match.end()] == "{":
            brace = match.end()
            end = contract_probe._find_matching(body, brace, "{", "}")  # noqa: SLF001
            fragment = body[brace + 1 : end] if end is not None else ""
        else:
            fragment = body[match.end() : match.end() + 500]
        method_match = re.search(rf"\b{re.escape(params[0])}\.(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*{re.escape(params[2])}\s*,\s*{re.escape(params[1])}\s*\)", fragment)
        if method_match:
            method = method_match.group("method")
            return {"resolved": method in _SAFE_METHODS, "method": method if method in _SAFE_METHODS else "non-allowlisted", "parameterCount": len(params)}
    return {"resolved": False}


def _get_tld_call(body: str) -> dict[str, Any] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    helper_aliases = [item["local"] for item in imports if item["source_module_id"] == HELPER_MODULE_ID]
    for alias in helper_aliases:
        match = re.search(rf"(?:\(\s*0\s*,\s*)?{re.escape(alias)}\.getTldHost\s*\)?\s*\(", body)
        if not match:
            continue
        open_paren = body.find("(", match.start(), match.end())
        # If the first '(' is the comma-operator wrapper, use the call paren after getTldHost.
        marker = body.find("getTldHost", match.start(), match.end())
        open_paren = body.find("(", marker)
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        classified = []
        for arg in args[:3]:
            clean = arg.strip()
            source = auth_probe._resolve_expression_source(body, clean)  # noqa: SLF001
            if source:
                classified.append({"kind": "webpack-source", **source})
            elif re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", clean):
                classified.append({"kind": "local-alias", "alias_hash": dataflow_probe._alias(COMPOSITION_MODULE_ID, clean)})  # noqa: SLF001
            else:
                classified.append({"kind": "expression"})
        return {"argumentCount": len(args), "arguments": classified}
    return None


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    helper = None
    composition = None
    members: dict[str, dict[str, str]] = {}
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] == HELPER_MODULE_ID and helper is None:
                helper = module["body"]
                members[HELPER_MODULE_ID] = {"member_path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest()}
            elif module["module_id"] == COMPOSITION_MODULE_ID and composition is None:
                composition = module["body"]
                members[COMPOSITION_MODULE_ID] = {"member_path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest()}
    return {
        "format": "musicark-yandex-upload-tld-method-v1",
        "source": "asar-getTldHost-standard-method-semantics",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "members": members,
        "getTldHost": _get_tld_method(helper or ""),
        "stage1Call": _get_tld_call(composition or ""),
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
    parser = argparse.ArgumentParser(description="Resolve getTldHost standard-method semantics safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized getTldHost method report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
