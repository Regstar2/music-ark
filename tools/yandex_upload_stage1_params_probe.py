"""Trace the exact ``params`` object passed to the stage-one request resource.

V35 proves that ``31322.X`` falls back to ``this.config.params.common.oauth``.
This probe inspects the second object argument supplied to ``new 12690.S`` and
emits safe schema keys, stable non-sensitive webpack source module/export
references, normalized structural expression tokens, and getter property names.
No OAuth value, credential, arbitrary string, sensitive member name, or raw
local name is emitted.
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
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
STAGE1_MODULE_ID = "12690"
_SEMANTIC_KEYS = {"params", "common", "oauth", "prefixUrl", "headers", "clientRemoteType"}
_SENSITIVE_NAME_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)",
    re.IGNORECASE,
)
_MODULE_MEMBER_TOKEN_RE = re.compile(r"^(?P<prefix>m\d+)\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{0,100})$")
_GETTER_RE = re.compile(r"\bget\s+(?P<key>[A-Za-z_$][A-Za-z0-9_$]{0,100})\s*\(\s*\)\s*\{")


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _stage1_config_arg(body: str) -> tuple[str | None, list[dict[str, str]]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    aliases = [item["local"] for item in imports if item["source_module_id"] == STAGE1_MODULE_ID]
    for alias in aliases:
        match = re.search(rf"\bnew\s+{re.escape(alias)}\.S\s*\(", body)
        if not match:
            continue
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1:end])  # noqa: SLF001
        if len(args) >= 2:
            return args[1].strip(), imports
    return None, imports


def _semantic_keys(expression: str) -> list[str]:
    return [key for key in sorted(_SEMANTIC_KEYS) if re.search(rf"\b{re.escape(key)}\b", expression)]


def _import_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})")
        found_member = False
        for match in member_pattern.finditer(expression):
            member = match.group("member")
            if _SENSITIVE_NAME_RE.search(member):
                found_member = True
                continue
            record = {"source_module_id": item["source_module_id"], "export_key": member}
            if record not in results:
                results.append(record)
            found_member = True
        if not found_member and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:100]


def _safe_normalized(expression: str, imports: list[dict[str, str]]) -> list[str]:
    tokens = prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, expression, imports)  # noqa: SLF001
    sanitized: list[str] = []
    for token in tokens:
        match = _MODULE_MEMBER_TOKEN_RE.fullmatch(token)
        if match and _SENSITIVE_NAME_RE.search(match.group("member")):
            sanitized.append(f"{match.group('prefix')}.<redacted-sensitive-member>")
        else:
            sanitized.append(token)
    return sanitized


def _safe_object_properties(expression: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    value = expression.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return []
    results: list[dict[str, Any]] = []
    for part in contract_probe._split_top_level(value[1:-1]):  # noqa: SLF001
        colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
        if colon is None:
            continue
        raw_key = part[:colon].strip().strip("\"'")
        key = contract_probe._safe_key(raw_key)  # noqa: SLF001
        if key is None:
            continue
        rhs = part[colon + 1:].strip()
        results.append({
            "key": key,
            "sourceRefs": _import_refs(rhs, imports),
            "normalized": _safe_normalized(rhs, imports),
        })
    return results[:100]


def _safe_getters(expression: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Return getter schema names and structural return provenance only."""
    value = expression.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return []
    results: list[dict[str, Any]] = []
    for match in _GETTER_RE.finditer(value):
        key = contract_probe._safe_key(match.group("key"))  # noqa: SLF001
        if key is None:
            continue
        brace = value.find("{", match.start(), match.end())
        end = contract_probe._find_matching(value, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        fragment = value[brace + 1:end]
        returns: list[dict[str, Any]] = []
        for return_match in re.finditer(r"\breturn\b", fragment):
            rhs = prefix_probe._slice_rhs(fragment, return_match.end())  # noqa: SLF001
            if not rhs:
                continue
            item = {
                "sourceRefs": _import_refs(rhs, imports),
                "normalized": _safe_normalized(rhs, imports),
            }
            if item not in returns:
                returns.append(item)
        results.append({"key": key, "returns": returns[:20]})
    return results[:100]


def _object_semantics(expression: str, imports: list[dict[str, str]]) -> dict[str, Any]:
    value = expression.strip()
    result: dict[str, Any] = {
        "kind": "object" if value.startswith("{") and value.endswith("}") else "expression",
        "semanticKeys": _semantic_keys(value),
        "objectKeys": contract_probe._object_keys(value) if value.startswith("{") else [],  # noqa: SLF001
        "propertySources": _safe_object_properties(value, imports),
        "getters": _safe_getters(value, imports),
        "sourceRefs": _import_refs(value, imports),
        "normalized": _safe_normalized(value, imports),
    }
    common_rhs = prefix_probe._object_property_rhs(value, "common")  # noqa: SLF001
    if common_rhs is not None:
        result["common"] = {
            "semanticKeys": _semantic_keys(common_rhs),
            "objectKeys": contract_probe._object_keys(common_rhs) if common_rhs.strip().startswith("{") else [],  # noqa: SLF001
            "propertySources": _safe_object_properties(common_rhs, imports),
            "getters": _safe_getters(common_rhs, imports),
            "sourceRefs": _import_refs(common_rhs, imports),
            "normalized": _safe_normalized(common_rhs, imports),
        }
    return result


def analyze_body(body: str) -> dict[str, Any]:
    config_arg, imports = _stage1_config_arg(body)
    if config_arg is None:
        return {"stage1ConstructorFound": False}
    params_rhs = prefix_probe._object_property_rhs(config_arg, "params")  # noqa: SLF001
    if params_rhs is None:
        return {"stage1ConstructorFound": True, "paramsFound": False}
    return {
        "stage1ConstructorFound": True,
        "paramsFound": True,
        "params": _object_semantics(params_rhs, imports),
        "oauthSemanticPresent": bool(re.search(r"\boauth\b", params_rhs)),
        "commonSemanticPresent": bool(re.search(r"\bcommon\b", params_rhs)),
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
            if module["module_id"] == COMPOSITION_MODULE_ID:
                matches.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": COMPOSITION_MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-stage1-params-v3",
        "source": "asar-stage1-params-common-oauth-provenance",
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
    parser = argparse.ArgumentParser(description="Trace the stage-one params/common/oauth object safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one params report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
