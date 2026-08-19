"""Resolve the stage-one prefix factory without exposing minified identifiers.

V21 proved that the upload resource prefix is constructed as a call to
``91953.getTldHost`` using module ``32732``, one runtime-derived alias and
``91953.TLD_MARK``. This probe narrows only those stable modules plus the exact
hashed composition method referenced by V21.

Output is limited to stable webpack export keys/module IDs, hashed local method
or symbol identifiers, allowlisted upload/config anchors, structural expression
kinds, safe public Yandex URL/domain literals and normalized return expressions.
No credentials, arbitrary strings, raw local identifiers or source contexts are
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
import yandex_upload_export_alias_probe as export_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
PREFIX_VALUE_MODULE_ID = "32732"
TLD_HELPER_MODULE_ID = "91953"
V21_METHOD_HASH = "alias:438f00411d67"
V21_TLD_MEMBER_HASH = "this.member:alias:63e3f2cf0f4a"
ALLOWLISTED_ANCHORS = (
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "prefixUrl",
    "clientSafeConfig",
    "clientRemoteType",
    "getApiPrefixUrl",
    "getClientSafeConfig",
    "getTldHost",
    "TLD_MARK",
    "tld",
)
_METHOD_RE = re.compile(r"(?<![A-Za-z0-9_$])(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\((?P<params>[^()]*)\)\s*\{")
_FUNCTION_ASSIGN_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:function\s*)?\((?P<params>[^()]*)\)\s*=>?\s*\{?"
)
_RETURN_RE = re.compile(r"\breturn\b")


def _hash_local(module_id: str, value: str) -> str:
    return dataflow_probe._alias(module_id, value)  # noqa: SLF001


def _function_body(text: str, brace: int) -> str | None:
    end = contract_probe._find_matching(text, brace, "{", "}")  # noqa: SLF001
    if end is None:
        return None
    return text[brace + 1 : end]


def _return_expressions(body: str) -> list[str]:
    results: list[str] = []
    for match in _RETURN_RE.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs and rhs not in results:
            results.append(rhs)
    return results[:20]


def _normalize_with_params(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    params: list[str],
) -> list[str]:
    normalized = prefix_probe._normalized_expression(module_id, expression, imports)  # noqa: SLF001
    replacements = {
        _hash_local(module_id, param): f"param:{index}"
        for index, param in enumerate(params)
        if param
    }
    return [replacements.get(token, token) for token in normalized]


def _method_record(module_id: str, body: str, method_name: str, params_text: str, method_body: str, imports: list[dict[str, str]]) -> dict[str, Any]:
    params = [item.strip() for item in contract_probe._split_top_level(params_text) if item.strip()]  # noqa: SLF001
    return {
        "method_hash": _hash_local(module_id, method_name),
        "parameter_count": len(params),
        "anchors": [anchor for anchor in ALLOWLISTED_ANCHORS if anchor in method_body],
        "normalized_returns": [
            _normalize_with_params(module_id, expression, imports, params)
            for expression in _return_expressions(method_body)
        ],
    }


def _composition_target_method(body: str) -> dict[str, Any] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    for match in _METHOD_RE.finditer(body):
        method_hash = _hash_local(COMPOSITION_MODULE_ID, match.group("name"))
        if method_hash != V21_METHOD_HASH:
            continue
        method_body = _function_body(body, match.end() - 1)
        if method_body is None:
            continue
        record = _method_record(
            COMPOSITION_MODULE_ID,
            body,
            match.group("name"),
            match.group("params"),
            method_body,
            imports,
        )
        record["v21_tld_member_hash"] = V21_TLD_MEMBER_HASH
        return record
    return None


def _safe_export_symbol(module_id: str, symbol: str) -> str:
    local = symbol.split(".")[-1]
    return _hash_local(module_id, local)


def _module_exports(module_id: str, body: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in export_probe._all_named_exports(body):  # noqa: SLF001
        results.append(
            {
                "export_key": item["export_name"],
                "local_symbol_hash": _safe_export_symbol(module_id, item["symbol"]),
            }
        )
    return results[:120]


def _safe_yandex_literals(body: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(body, index)  # noqa: SLF001
        safe = prefix_probe._safe_yandex_literal(value)  # noqa: SLF001
        if safe and safe not in results:
            results.append(safe)
    return results[:80]


def _export_function_role(module_id: str, body: str, export_key: str) -> dict[str, Any] | None:
    exports = export_probe._all_named_exports(body)  # noqa: SLF001
    selected = next((item for item in exports if item["export_name"] == export_key), None)
    if selected is None:
        return None
    symbol = selected["symbol"].split(".")[-1]
    imports = wiring_probe._imports(body)  # noqa: SLF001

    # function name(...) { ... }
    pattern = re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\((?P<params>[^()]*)\)\s*\{{")
    match = pattern.search(body)
    if match:
        method_body = _function_body(body, match.end() - 1)
        if method_body is not None:
            record = _method_record(module_id, body, symbol, match.group("params"), method_body, imports)
            return {"export_key": export_key, **record}

    # symbol=function(...) { ... } / symbol=(...)=>{ ... }
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?:function\s*)?\((?P<params>[^()]*)\)\s*(?:=>)?\s*\{{"
    )
    match = pattern.search(body)
    if match:
        method_body = _function_body(body, match.end() - 1)
        if method_body is not None:
            record = _method_record(module_id, body, symbol, match.group("params"), method_body, imports)
            return {"export_key": export_key, **record}

    # Concise one-argument arrow functions are also common in minified bundles.
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?P<param>[A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*(?P<expr>[^,;]+)"
    )
    match = pattern.search(body)
    if match:
        return {
            "export_key": export_key,
            "method_hash": _hash_local(module_id, symbol),
            "parameter_count": 1,
            "anchors": [anchor for anchor in ALLOWLISTED_ANCHORS if anchor in match.group("expr")],
            "normalized_returns": [
                _normalize_with_params(module_id, match.group("expr"), imports, [match.group("param")])
            ],
        }
    return {"export_key": export_key, "method_hash": _hash_local(module_id, symbol), "definition": "unresolved"}


def analyze_modules(composition_body: str, prefix_value_body: str, helper_body: str) -> dict[str, Any]:
    return {
        "composition": {
            "module_id": COMPOSITION_MODULE_ID,
            "target_method": _composition_target_method(composition_body),
        },
        "prefix_value": {
            "module_id": PREFIX_VALUE_MODULE_ID,
            "exports": _module_exports(PREFIX_VALUE_MODULE_ID, prefix_value_body),
            "public_yandex_literals": _safe_yandex_literals(prefix_value_body),
            "anchors": [anchor for anchor in ALLOWLISTED_ANCHORS if anchor in prefix_value_body],
        },
        "tld_helper": {
            "module_id": TLD_HELPER_MODULE_ID,
            "exports": _module_exports(TLD_HELPER_MODULE_ID, helper_body),
            "getTldHost": _export_function_role(TLD_HELPER_MODULE_ID, helper_body, "getTldHost"),
            "TLD_MARK": next(
                (
                    {"export_key": item["export_name"], "local_symbol_hash": _safe_export_symbol(TLD_HELPER_MODULE_ID, item["symbol"])}
                    for item in export_probe._all_named_exports(helper_body)  # noqa: SLF001
                    if item["export_name"] == "TLD_MARK"
                ),
                None,
            ),
            "public_yandex_literals": _safe_yandex_literals(helper_body),
        },
    }


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    found: dict[str, list[dict[str, Any]]] = {module_id: [] for module_id in (COMPOSITION_MODULE_ID, PREFIX_VALUE_MODULE_ID, TLD_HELPER_MODULE_ID)}

    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            module_id = module["module_id"]
            if module_id not in found:
                continue
            found[module_id].append(
                {
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "body": module["body"],
                }
            )

    analyses: list[dict[str, Any]] = []
    for composition in found[COMPOSITION_MODULE_ID]:
        for prefix_value in found[PREFIX_VALUE_MODULE_ID]:
            for helper in found[TLD_HELPER_MODULE_ID]:
                analyses.append(
                    {
                        "members": {
                            COMPOSITION_MODULE_ID: {k: v for k, v in composition.items() if k != "body"},
                            PREFIX_VALUE_MODULE_ID: {k: v for k, v in prefix_value.items() if k != "body"},
                            TLD_HELPER_MODULE_ID: {k: v for k, v in helper.items() if k != "body"},
                        },
                        **analyze_modules(composition["body"], prefix_value["body"], helper["body"]),
                    }
                )

    return {
        "format": "musicark-yandex-upload-prefix-factory-v1",
        "source": "asar-targeted-prefix-factory-semantics",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "analyses": analyses[:30],
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
    parser = argparse.ArgumentParser(description="Resolve Yandex upload stage-one prefix factory semantics.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one prefix factory report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
