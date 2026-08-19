"""Trace stage-one HTTP/auth dependencies without emitting credentials.

The stage-one upload resource is known to be webpack export ``12690.S`` and is
constructed in composition module ``7644`` with two arguments. This probe
resolves the class base, the exact source of constructor argument zero, and the
request/header helper modules involved in the inherited HTTP options path.
Only stable module/export keys, allowlisted property/method names, booleans and
hashed local symbols are emitted.
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
import yandex_upload_target_probe as target_probe


STAGE1_MODULE_ID = "12690"
COMPOSITION_MODULE_ID = "7644"
REQUEST_MODULE_ID = "31322"
HEADER_MODULE_ID = "37558"
HTTP_CLIENT_MODULE_ID = "74187"
TARGET_IDS = {STAGE1_MODULE_ID, COMPOSITION_MODULE_ID, REQUEST_MODULE_ID, HEADER_MODULE_ID, HTTP_CLIENT_MODULE_ID}
ALLOWLIST = (
    "getUploadUrl",
    "loader/upload-url",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "httpClient",
    "authorization",
    "headers",
    "prefixUrl",
    "clientRemoteType",
    "clientSafeConfig",
    "customApiToken",
    "customApiPrefixUrl",
    "oauth",
    "session",
)
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_SAFE_MEMBER_RE = re.compile(r"^(?P<base>[A-Za-z_$][A-Za-z0-9_$]{0,100})(?:\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{0,100}))?$")


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
    base = match.group("base")
    member = match.group("member") or "<module-object>"
    for item in wiring_probe._imports(body):  # noqa: SLF001
        if item["local"] == base:
            return {"source_module_id": item["source_module_id"], "export_key": member}
    return None


def _assignment(body: str, symbol: str) -> str | None:
    if not _SAFE_IDENTIFIER_RE.fullmatch(symbol):
        return None
    match = re.search(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?!=|>)", body)
    if not match:
        return None
    # A simple identifier/member RHS is enough for provenance; never persist the source.
    tail = body[match.end() : match.end() + 240]
    simple = re.match(r"\s*(?P<expr>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?)", tail)
    return simple.group("expr") if simple else None


def _resolve_expression_source(body: str, expression: str) -> dict[str, str] | None:
    direct = _resolve_import(body, expression)
    if direct:
        return direct
    if _SAFE_IDENTIFIER_RE.fullmatch(expression.strip()):
        rhs = _assignment(body, expression.strip())
        if rhs:
            return _resolve_import(body, rhs)
    return None


def _class_for_export(module_id: str, body: str, export_key: str) -> dict[str, Any] | None:
    symbol = _exports(body).get(export_key)
    if not symbol:
        return None
    local = symbol.split(".")[-1]
    for span in export_probe._class_spans(body):  # noqa: SLF001
        if local not in {span.get("assigned_symbol"), span.get("class_name")}:
            continue
        fragment = body[span["start"] : span["end"]]
        extends_raw = str(span.get("extends") or "")
        return {
            "export_key": export_key,
            "local_symbol_hash": _hash(module_id, local),
            "extendsPresent": bool(extends_raw),
            "extendsSource": _resolve_import(body, extends_raw) if extends_raw else None,
            "anchors": [name for name in ALLOWLIST if name in fragment],
        }
    return {
        "export_key": export_key,
        "local_symbol_hash": _hash(module_id, local),
        "extendsPresent": False,
        "extendsSource": None,
        "anchors": [],
    }


def _module_summary(module_id: str, body: str) -> dict[str, Any]:
    exports = []
    for item in export_probe._all_named_exports(body):  # noqa: SLF001
        local = item["symbol"].split(".")[-1]
        exports.append({"export_key": item["export_name"], "local_symbol_hash": _hash(module_id, local)})
    imports = sorted({item["source_module_id"] for item in wiring_probe._imports(body)})  # noqa: SLF001
    return {
        "module_id": module_id,
        "anchors": [name for name in ALLOWLIST if name in body],
        "exports": exports[:160],
        "import_module_ids": imports[:200],
    }


def _stage1_constructor(composition_body: str) -> dict[str, Any] | None:
    imports = wiring_probe._imports(composition_body)  # noqa: SLF001
    aliases = [item["local"] for item in imports if item["source_module_id"] == STAGE1_MODULE_ID]
    for alias in aliases:
        match = re.search(rf"\bnew\s+{re.escape(alias)}\.S\s*\(", composition_body)
        if not match:
            continue
        open_paren = composition_body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(composition_body, open_paren, "(", ")")  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(composition_body[open_paren + 1 : end])  # noqa: SLF001
        first = args[0].strip() if args else ""
        second = args[1] if len(args) > 1 else ""
        config_names = [name for name in ("prefixUrl", "authorization", "headers", "customApiToken", "customApiPrefixUrl", "clientRemoteType") if re.search(rf"\b{re.escape(name)}\b", second)]
        return {
            "export_key": "S",
            "argument_count": len(args),
            "argument0Source": _resolve_expression_source(composition_body, first),
            "argument1ConfigProperties": config_names,
            "customApiTokenPassedDirectly": "customApiToken" in config_names,
            "authorizationPassedDirectly": "authorization" in config_names,
        }
    return None


def analyze_modules(modules: dict[str, str]) -> dict[str, Any]:
    stage1 = modules.get(STAGE1_MODULE_ID, "")
    composition = modules.get(COMPOSITION_MODULE_ID, "")
    request = modules.get(REQUEST_MODULE_ID, "")
    header = modules.get(HEADER_MODULE_ID, "")
    http_client = modules.get(HTTP_CLIENT_MODULE_ID, "")
    stage1_class = _class_for_export(STAGE1_MODULE_ID, stage1, "S") if stage1 else None
    request_roles = []
    if request:
        for export_key in _exports(request):
            role = _class_for_export(REQUEST_MODULE_ID, request, export_key)
            if role and role["anchors"]:
                request_roles.append(role)
    return {
        "stage1": {
            "class": stage1_class,
            "constructor": _stage1_constructor(composition) if composition else None,
        },
        "requestModule": _module_summary(REQUEST_MODULE_ID, request) if request else None,
        "requestClassRoles": request_roles[:40],
        "headerModule": _module_summary(HEADER_MODULE_ID, header) if header else None,
        "httpClientModule": _module_summary(HTTP_CLIENT_MODULE_ID, http_client) if http_client else None,
        "staticAuthorizationCandidate": (
            "custom-api-token-direct" if (_stage1_constructor(composition) or {}).get("customApiTokenPassedDirectly")
            else "constructor-arg0-or-inherited-request-layer"
        ),
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    records: dict[str, list[dict[str, Any]]] = {module_id: [] for module_id in TARGET_IDS}
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            module_id = module["module_id"]
            if module_id in records:
                records[module_id].append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "body": module["body"],
                })
    selected = {module_id: values[0]["body"] for module_id, values in records.items() if values}
    members = {
        module_id: [{"member_path": item["member_path"], "member_sha256": item["member_sha256"]} for item in values[:6]]
        for module_id, values in records.items() if values
    }
    return {
        "format": "musicark-yandex-upload-stage1-auth-lineage-v1",
        "source": "asar-stage1-http-auth-dependency-lineage",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "members": members,
        "analysis": analyze_modules(selected),
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
    parser = argparse.ArgumentParser(description="Trace Yandex upload stage-one auth dependencies safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one auth lineage report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
