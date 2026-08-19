"""Trace the value used by the stage-one OAuth Authorization header.

The proven request class is ``31322.X``. This probe correlates constructor
parameters, ``this.<property>`` assignments and the variable/member consumed by
the ``authorization`` object binding. Non-allowlisted property/local names are
hashed; credential values and source contexts are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_auth_semantics_probe as auth_semantics
import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_request_stack_probe as stack_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


MODULE_ID = "31322"
EXPORT_KEY = "X"
_ALLOWLISTED_PROPERTIES = {"oauth", "authorization", "httpClient", "headers", "prefixUrl", "clientRemoteType"}
_JS_SKIP = set(dataflow_probe._JS_KEYWORDS) | {"OAuth", "concat"}  # noqa: SLF001
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")


def _hash(value: str) -> str:
    return dataflow_probe._alias(MODULE_ID, value)  # noqa: SLF001


def _safe_property(value: str) -> str:
    return value if value in _ALLOWLISTED_PROPERTIES else "property:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _constructor_details(class_fragment: str) -> dict[str, Any] | None:
    match = re.search(r"\bconstructor\s*\((?P<params>[^()]*)\)\s*\{", class_fragment)
    if not match:
        return None
    brace = class_fragment.find("{", match.start(), match.end())
    end = contract_probe._find_matching(class_fragment, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
    if end is None:
        return None
    params = [item.strip() for item in contract_probe._split_top_level(match.group("params")) if item.strip()]  # noqa: SLF001
    param_index = {param: index for index, param in enumerate(params)}
    fragment = class_fragment[brace + 1:end]
    assignments: list[dict[str, Any]] = []
    pattern = re.compile(r"\bthis\.(?P<property>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?P<rhs>[^;,}]+)")
    for item in pattern.finditer(fragment):
        prop = item.group("property")
        rhs = item.group("rhs").strip()
        source: dict[str, Any] = {"kind": "expression"}
        if rhs in param_index:
            source = {"kind": "constructor-param", "index": param_index[rhs]}
        else:
            member = re.fullmatch(r"(?P<base>[A-Za-z_$][A-Za-z0-9_$]*)\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)", rhs)
            if member and member.group("base") in param_index:
                source = {
                    "kind": "constructor-param-member",
                    "index": param_index[member.group("base")],
                    "member": _safe_property(member.group("member")),
                }
            elif re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", rhs):
                source = {"kind": "local-alias", "aliasHash": _hash(rhs)}
            else:
                source = {"kind": "expression", "normalized": prefix_probe._normalized_expression(MODULE_ID, rhs, [])}  # noqa: SLF001
        assignments.append({"property": _safe_property(prop), "source": source})
    return {
        "parameterCount": len(params),
        "parameterHashes": [{"index": index, "aliasHash": _hash(param)} for index, param in enumerate(params)],
        "propertyAssignments": assignments[:80],
    }


def _authorization_rhs(class_fragment: str) -> str | None:
    for pattern in (
        re.compile(r"(?<![A-Za-z0-9_$])authorization\s*:\s*"),
        re.compile(r"[\"']authorization[\"']\s*:\s*"),
    ):
        match = pattern.search(class_fragment)
        if match:
            return prefix_probe._slice_rhs(class_fragment, match.end())  # noqa: SLF001
    return None


def _rhs_origins(rhs: str, constructor: dict[str, Any] | None) -> dict[str, Any]:
    param_hashes = {item["aliasHash"]: item["index"] for item in (constructor or {}).get("parameterHashes", [])}
    property_assignments = (constructor or {}).get("propertyAssignments", [])
    aliases: list[dict[str, Any]] = []
    this_properties: list[str] = []
    for prop in re.findall(r"\bthis\.([A-Za-z_$][A-Za-z0-9_$]*)", rhs):
        safe = _safe_property(prop)
        if safe not in this_properties:
            this_properties.append(safe)
    # Remove property names from bare-identifier candidates by excluding tokens
    # immediately preceded by a dot and standard syntax identifiers.
    for match in _IDENTIFIER_RE.finditer(rhs):
        name = match.group(0)
        if name in _JS_SKIP or name in _ALLOWLISTED_PROPERTIES:
            continue
        if match.start() > 0 and rhs[match.start() - 1] == ".":
            continue
        alias_hash = _hash(name)
        item: dict[str, Any] = {"aliasHash": alias_hash}
        if alias_hash in param_hashes:
            item["origin"] = {"kind": "constructor-param", "index": param_hashes[alias_hash]}
        else:
            item["origin"] = {"kind": "local-or-closure"}
        if item not in aliases:
            aliases.append(item)
    linked_assignments = [item for item in property_assignments if item["property"] in this_properties]
    return {
        "publicScheme": "OAuth" if "OAuth" in auth_semantics._public_schemes(rhs) else None,  # noqa: SLF001
        "thisProperties": this_properties,
        "linkedConstructorAssignments": linked_assignments,
        "bareAliases": aliases[:40],
    }


def analyze_body(body: str) -> dict[str, Any]:
    found = stack_probe._class_span(body, EXPORT_KEY)  # noqa: SLF001
    if not found:
        return {"classResolved": False}
    _, _, class_fragment = found
    constructor = _constructor_details(class_fragment)
    rhs = _authorization_rhs(class_fragment)
    return {
        "classResolved": True,
        "constructor": constructor,
        "authorizationBindingFound": rhs is not None,
        "authorizationOrigin": _rhs_origins(rhs, constructor) if rhs else None,
        "customApiTokenReferenced": "customApiToken" in class_fragment,
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    analyses: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] == MODULE_ID:
                analyses.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-oauth-origin-v1",
        "source": "asar-stage1-oauth-constructor-origin",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "analyses": analyses[:20],
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
    parser = argparse.ArgumentParser(description="Trace stage-one OAuth value origin safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized OAuth-origin report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
