"""Trace the upload stage-one request inheritance stack and option semantics.

Starting from the proven resource ``12690.S``, this probe follows only webpack
class ``extends`` edges. For each class it emits stable module/export IDs,
allowlisted request/auth property names, constructor parameter wiring and
allowlisted method summaries. No source contexts, scalar strings, header values
or credentials are emitted.
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


START_MODULE_ID = "12690"
START_EXPORT_KEY = "S"
EXTRA_MODULE_IDS = ("74187", "91945", "37558")
ALLOWLIST = (
    "getUploadUrl",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "httpClient",
    "authorization",
    "headers",
    "prefixUrl",
    "oauth",
    "session",
    "clientRemoteType",
    "clientSafeConfig",
    "body",
    "searchParams",
    "signal",
    "timeout",
)
METHODS = ("createHttpOptions", "createRequestHeaders", "createSessionRequestHeaders")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_SAFE_MEMBER_RE = re.compile(r"^(?P<base>[A-Za-z_$][A-Za-z0-9_$]{0,100})\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{0,100})$")


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


def _resolve_import(body: str, expression: str) -> dict[str, str] | None:
    match = _SAFE_MEMBER_RE.fullmatch(expression.strip())
    if not match:
        return None
    for item in wiring_probe._imports(body):  # noqa: SLF001
        if item["local"] == match.group("base"):
            return {"source_module_id": item["source_module_id"], "export_key": match.group("member")}
    return None


def _class_span(body: str, export_key: str) -> tuple[str, dict[str, Any], str] | None:
    symbol = _exports(body).get(export_key)
    if not symbol:
        return None
    local = symbol.split(".")[-1]
    for span in export_probe._class_spans(body):  # noqa: SLF001
        if local in {span.get("assigned_symbol"), span.get("class_name")}:
            return local, span, body[span["start"] : span["end"]]
    return None


def _params(text: str) -> list[str]:
    return [item.strip() for item in contract_probe._split_top_level(text) if item.strip()]  # noqa: SLF001


def _normalized_returns(module_id: str, fragment: str, imports: list[dict[str, str]], params: list[str]) -> list[list[str]]:
    results: list[list[str]] = []
    replacements = {_hash(module_id, param): f"param:{index}" for index, param in enumerate(params)}
    for match in re.finditer(r"\breturn\b", fragment):
        rhs = prefix_probe._slice_rhs(fragment, match.end())  # noqa: SLF001
        if not rhs:
            continue
        tokens = prefix_probe._normalized_expression(module_id, rhs, imports)  # noqa: SLF001
        normalized = [replacements.get(token, token) for token in tokens]
        if normalized not in results:
            results.append(normalized)
    return results[:12]


def _import_member_refs(body: str, fragment: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in wiring_probe._imports(body):  # noqa: SLF001
        pattern = re.compile(rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})")
        for match in pattern.finditer(fragment):
            record = {"source_module_id": item["source_module_id"], "export_key": match.group("member")}
            if record not in results:
                results.append(record)
    return results[:80]


def _method_summary(module_id: str, body: str, class_fragment: str, method_name: str) -> dict[str, Any] | None:
    pattern = re.compile(rf"(?<![.$A-Za-z0-9_$])(?:async\s+)?{re.escape(method_name)}\s*\((?P<params>[^()]*)\)\s*\{{")
    match = pattern.search(class_fragment)
    if not match:
        return None
    brace = class_fragment.find("{", match.start(), match.end())
    end = contract_probe._find_matching(class_fragment, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
    if end is None:
        return None
    params = _params(match.group("params"))
    fragment = class_fragment[brace + 1 : end]
    return {
        "name": method_name,
        "parameterCount": len(params),
        "allowlistedNames": [name for name in ALLOWLIST if name in fragment],
        "importMemberRefs": _import_member_refs(body, fragment),
        "normalizedReturns": _normalized_returns(module_id, fragment, wiring_probe._imports(body), params),  # noqa: SLF001
    }


def _constructor_summary(module_id: str, class_fragment: str) -> dict[str, Any] | None:
    match = re.search(r"\bconstructor\s*\((?P<params>[^()]*)\)\s*\{", class_fragment)
    if not match:
        return None
    brace = class_fragment.find("{", match.start(), match.end())
    end = contract_probe._find_matching(class_fragment, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
    if end is None:
        return None
    params = _params(match.group("params"))
    param_index = {param: index for index, param in enumerate(params)}
    fragment = class_fragment[brace + 1 : end]
    assignments: list[dict[str, Any]] = []
    for name in ALLOWLIST:
        pattern = re.compile(rf"\bthis\.{re.escape(name)}\s*=\s*(?P<rhs>[A-Za-z_$][A-Za-z0-9_$]*)")
        for item in pattern.finditer(fragment):
            rhs = item.group("rhs")
            record = {"property": name, "source": f"param:{param_index[rhs]}" if rhs in param_index else "local"}
            if record not in assignments:
                assignments.append(record)
    return {"parameterCount": len(params), "allowlistedAssignments": assignments}


def _class_info(module_id: str, body: str, export_key: str) -> dict[str, Any] | None:
    found = _class_span(body, export_key)
    if not found:
        return None
    local, span, fragment = found
    extends_raw = str(span.get("extends") or "")
    methods = [summary for name in METHODS if (summary := _method_summary(module_id, body, fragment, name)) is not None]
    return {
        "module_id": module_id,
        "export_key": export_key,
        "local_symbol_hash": _hash(module_id, local),
        "extendsSource": _resolve_import(body, extends_raw) if extends_raw else None,
        "allowlistedNames": [name for name in ALLOWLIST if name in fragment],
        "constructor": _constructor_summary(module_id, fragment),
        "methods": methods,
    }


def _follow_stack(index: dict[str, str], *, max_depth: int = 8) -> list[dict[str, Any]]:
    module_id, export_key = START_MODULE_ID, START_EXPORT_KEY
    stack: list[dict[str, Any]] = []
    visited: set[tuple[str, str]] = set()
    for _ in range(max_depth):
        state = (module_id, export_key)
        if state in visited:
            break
        visited.add(state)
        body = index.get(module_id)
        if not body:
            stack.append({"module_id": module_id, "export_key": export_key, "resolution": "module-missing"})
            break
        info = _class_info(module_id, body, export_key)
        if not info:
            stack.append({"module_id": module_id, "export_key": export_key, "resolution": "class-unresolved"})
            break
        stack.append(info)
        next_source = info.get("extendsSource")
        if not isinstance(next_source, dict):
            break
        module_id = next_source["source_module_id"]
        export_key = next_source["export_key"]
    return stack


def _module_summary(module_id: str, body: str) -> dict[str, Any]:
    exports = []
    for item in export_probe._all_named_exports(body):  # noqa: SLF001
        exports.append({"export_key": item["export_name"], "local_symbol_hash": _hash(module_id, item["symbol"].split(".")[-1])})
    return {
        "module_id": module_id,
        "allowlistedNames": [name for name in ALLOWLIST if name in body],
        "exports": exports[:160],
        "importModuleIds": sorted({item["source_module_id"] for item in wiring_probe._imports(body)})[:200],  # noqa: SLF001
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    module_bodies: dict[str, str] = {}
    member_meta: dict[str, dict[str, str]] = {}
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            module_id = module["module_id"]
            if module_id not in module_bodies:
                module_bodies[module_id] = module["body"]
                member_meta[module_id] = {"member_path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest()}

    stack = _follow_stack(module_bodies)
    relevant_ids = {item.get("module_id") for item in stack if isinstance(item, dict)} | set(EXTRA_MODULE_IDS)
    summaries = [
        {**member_meta.get(module_id, {}), **_module_summary(module_id, module_bodies[module_id])}
        for module_id in sorted(relevant_ids)
        if module_id in module_bodies
    ]
    auth_modules = [
        item["module_id"]
        for item in stack
        if isinstance(item, dict) and any(name in (item.get("allowlistedNames") or []) for name in ("authorization", "oauth", "session"))
    ]
    return {
        "format": "musicark-yandex-upload-request-stack-v1",
        "source": "asar-stage1-request-inheritance-semantics",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "classStack": stack,
        "moduleSummaries": summaries,
        "authorizationCandidateModules": auth_modules,
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
    parser = argparse.ArgumentParser(description="Trace Yandex upload request class inheritance safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one request-stack report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
