"""Resolve ``getTldHost`` and the stage-one prefix namespace export values.

This is a narrow follow-up to V22. It binds the stable webpack export
``91953.getTldHost`` to its minified local symbol and supports named functions,
function assignments, braced arrows and concise arrows. It also normalizes the
RHS of module 32732 exports used by the stage-one prefix factory.

Output contains stable module/export keys, hashed local symbols, normalized
operators/parameter positions/module refs, structural value kinds and safe
public Yandex host templates only. Arbitrary strings, credentials and source
contexts are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_contract_probe as contract_probe
import yandex_upload_export_alias_probe as export_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


PREFIX_VALUE_MODULE_ID = "32732"
TLD_HELPER_MODULE_ID = "91953"
TARGET_EXPORTS = {PREFIX_VALUE_MODULE_ID: ("mZ", "pp"), TLD_HELPER_MODULE_ID: ("getTldHost", "TLD_MARK")}
_SENSITIVE_RE = re.compile(r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)", re.IGNORECASE)
_PUBLIC_YANDEX_TEMPLATE_RE = re.compile(
    r"^https?://[A-Za-z0-9._:{}-]*(?:yandex\.(?:ru|net|com)|yandex\{[^}]{1,40}\}|yandex\.[A-Za-z{}._-]{1,80})(?::\d+)?(?:/[A-Za-z0-9_./{}:-]*)?$",
    re.IGNORECASE,
)
_ASSIGNMENT_BOUNDARY_RE = re.compile(r"(?<![A-Za-z0-9_$])(?P<symbol>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*")


def _hash(module_id: str, value: str) -> str:
    return dataflow_probe._alias(module_id, value)  # noqa: SLF001


def _safe_public_template(value: str) -> str | None:
    clean = value.strip()
    if not clean or _SENSITIVE_RE.search(clean) or "?" in clean or "#" in clean:
        return None
    if _PUBLIC_YANDEX_TEMPLATE_RE.fullmatch(clean):
        return clean
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = (parsed.hostname or "").lower()
    if host == "yandex.ru" or host.endswith(".yandex.ru") or host == "yandex.net" or host.endswith(".yandex.net") or host == "yandex.com" or host.endswith(".yandex.com"):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))
    return None


def _normalize_expression(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    params: list[str] | None = None,
) -> list[str]:
    tokens = prefix_probe._normalized_expression(module_id, expression, imports)  # noqa: SLF001
    replacements = {
        _hash(module_id, param): f"param:{index}"
        for index, param in enumerate(params or [])
        if param
    }
    result: list[str] = []
    index = 0
    while index < len(tokens):
        token = replacements.get(tokens[index], tokens[index])
        result.append(token)
        index += 1
    return result


def _export_map(body: str) -> dict[str, str]:
    return {item["export_name"]: item["symbol"].split(".")[-1] for item in export_probe._all_named_exports(body)}  # noqa: SLF001


def _find_braced_function(body: str, symbol: str) -> tuple[list[str], str] | None:
    patterns = (
        re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\((?P<params>[^()]*)\)\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*function(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?\s*\((?P<params>[^()]*)\)\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*\((?P<params>[^()]*)\)\s*=>\s*\{{"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?P<param>[A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*\{{"),
    )
    for pattern in patterns:
        match = pattern.search(body)
        if not match:
            continue
        brace = body.find("{", match.start(), match.end())
        end = contract_probe._find_matching(body, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        params_text = match.groupdict().get("params")
        if params_text is not None:
            params = [item.strip() for item in contract_probe._split_top_level(params_text) if item.strip()]  # noqa: SLF001
        else:
            params = [match.group("param")]
        return params, body[brace + 1 : end]
    return None


def _find_concise_arrow(body: str, symbol: str) -> tuple[list[str], str] | None:
    patterns = (
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*\((?P<params>[^()]*)\)\s*=>\s*"),
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?P<param>[A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*"),
    )
    for pattern in patterns:
        match = pattern.search(body)
        if not match:
            continue
        if match.end() < len(body) and body[match.end()] == "{":
            continue
        params_text = match.groupdict().get("params")
        if params_text is not None:
            params = [item.strip() for item in contract_probe._split_top_level(params_text) if item.strip()]  # noqa: SLF001
        else:
            params = [match.group("param")]
        expression = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if expression:
            return params, expression
    return None


def _normalized_returns(module_id: str, function_body: str, imports: list[dict[str, str]], params: list[str]) -> list[list[str]]:
    results: list[list[str]] = []
    for match in re.finditer(r"\breturn\b", function_body):
        expression = prefix_probe._slice_rhs(function_body, match.end())  # noqa: SLF001
        if expression:
            normalized = _normalize_expression(module_id, expression, imports, params)
            if normalized not in results:
                results.append(normalized)
    return results[:20]


def resolve_function_export(module_id: str, body: str, export_key: str) -> dict[str, Any] | None:
    exports = _export_map(body)
    symbol = exports.get(export_key)
    if symbol is None:
        return None
    imports = wiring_probe._imports(body)  # noqa: SLF001
    base: dict[str, Any] = {"export_key": export_key, "local_symbol_hash": _hash(module_id, symbol)}

    braced = _find_braced_function(body, symbol)
    if braced is not None:
        params, function_body = braced
        return {
            **base,
            "definition": "braced-function",
            "parameter_count": len(params),
            "anchors": [anchor for anchor in ("getTldHost", "TLD_MARK", "tld") if anchor in function_body],
            "normalized_returns": _normalized_returns(module_id, function_body, imports, params),
        }

    concise = _find_concise_arrow(body, symbol)
    if concise is not None:
        params, expression = concise
        return {
            **base,
            "definition": "concise-arrow",
            "parameter_count": len(params),
            "normalized_returns": [_normalize_expression(module_id, expression, imports, params)],
        }
    return {**base, "definition": "unresolved"}


def _find_symbol_assignment(body: str, symbol: str) -> str | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?!=|>)")
    for match in pattern.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return rhs
    return None


def _public_literals_in_expression(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        safe = _safe_public_template(value)
        if safe and safe not in results:
            results.append(safe)
    return results[:40]


def resolve_value_export(module_id: str, body: str, export_key: str) -> dict[str, Any] | None:
    exports = _export_map(body)
    symbol = exports.get(export_key)
    if symbol is None:
        return None
    rhs = _find_symbol_assignment(body, symbol)
    imports = wiring_probe._imports(body)  # noqa: SLF001
    result: dict[str, Any] = {
        "export_key": export_key,
        "local_symbol_hash": _hash(module_id, symbol),
        "definitionFound": rhs is not None,
    }
    if rhs is not None:
        result["normalizedRhs"] = _normalize_expression(module_id, rhs, imports)
        result["publicYandexTemplates"] = _public_literals_in_expression(rhs)
    return result


def analyze_modules(prefix_body: str, helper_body: str) -> dict[str, Any]:
    return {
        "prefix_value": {
            "module_id": PREFIX_VALUE_MODULE_ID,
            "exports": [
                item
                for key in TARGET_EXPORTS[PREFIX_VALUE_MODULE_ID]
                if (item := resolve_value_export(PREFIX_VALUE_MODULE_ID, prefix_body, key)) is not None
            ],
        },
        "tld_helper": {
            "module_id": TLD_HELPER_MODULE_ID,
            "getTldHost": resolve_function_export(TLD_HELPER_MODULE_ID, helper_body, "getTldHost"),
            "TLD_MARK": resolve_value_export(TLD_HELPER_MODULE_ID, helper_body, "TLD_MARK"),
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
    found: dict[str, list[dict[str, Any]]] = {PREFIX_VALUE_MODULE_ID: [], TLD_HELPER_MODULE_ID: []}
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
    for prefix_value in found[PREFIX_VALUE_MODULE_ID]:
        for helper in found[TLD_HELPER_MODULE_ID]:
            analyses.append(
                {
                    "members": {
                        PREFIX_VALUE_MODULE_ID: {k: v for k, v in prefix_value.items() if k != "body"},
                        TLD_HELPER_MODULE_ID: {k: v for k, v in helper.items() if k != "body"},
                    },
                    **analyze_modules(prefix_value["body"], helper["body"]),
                }
            )
    return {
        "format": "musicark-yandex-upload-tld-helper-v1",
        "source": "asar-targeted-tld-helper-and-prefix-export-scan",
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
    parser = argparse.ArgumentParser(description="Resolve getTldHost and stage-one prefix namespace exports safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized getTldHost/prefix export report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
