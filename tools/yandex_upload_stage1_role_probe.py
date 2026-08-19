"""Resolve the stage-one upload resource export and its composition config map.

The probe is deliberately limited to webpack modules 12690 and 7644. It maps
stable webpack export keys to allowlisted upload methods/classes and summarizes
the exact object argument passed to ``new <module12690>.<export>(...)``.

Only protocol-relevant property names, numeric source module IDs, stable export
keys, hashed generic object keys/local aliases and structural kinds are emitted.
No scalar values, JavaScript source contexts, credentials, header/query values or
raw local identifiers are persisted.
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
import yandex_upload_export_alias_probe as export_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


STAGE1_MODULE_ID = "12690"
COMPOSITION_MODULE_ID = "7644"
ROLE_ANCHORS = (
    "getUploadUrl",
    "loader/upload-url",
    "uploadFile",
    "createHttpOptions",
    "httpClient",
)
_PROTOCOL_KEY_RE = re.compile(
    r"(?:ugc|upload|http|api|resource|client|prefix|auth|header|music|request|config|loader|track|playlist)",
    re.IGNORECASE,
)
_SAFE_KEY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$-]{0,100}$")
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")


def _hash_key(value: str) -> str:
    return "key:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _safe_key(value: str) -> str:
    clean = value.strip().strip("\"'")
    if not _SAFE_KEY_RE.fullmatch(clean):
        return "key:invalid"
    return clean if _PROTOCOL_KEY_RE.search(clean) else _hash_key(clean)


def _safe_kind(expression: str) -> dict[str, Any]:
    item = config_probe._expression_kind(expression)  # noqa: SLF001
    kind = str(item.get("kind") or "unknown")
    result: dict[str, Any] = {"kind": kind}
    if kind == "protocol-enum" and item.get("name") in {"YandexMusicDesktopApp", "YandexMusicWebNext"}:
        result["name"] = item["name"]
    return result


def _source_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        local = item["local"]
        source_id = item["source_module_id"]
        member_pattern = re.compile(rf"\b{re.escape(local)}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)")
        matched = False
        for match in member_pattern.finditer(expression):
            record = {"source_module_id": source_id, "export_key": match.group("member")}
            if record not in results:
                results.append(record)
            matched = True
        if not matched and re.search(rf"\b{re.escape(local)}\b", expression):
            record = {"source_module_id": source_id, "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _alias_refs(module_id: str, expression: str, imports: list[dict[str, str]]) -> list[str]:
    import_locals = {item["local"] for item in imports}
    results: list[str] = []
    for identifier in _IDENTIFIER_RE.findall(expression):
        if identifier in import_locals or identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
            continue
        if identifier in {
            "customApiPrefixUrl",
            "customApiToken",
            "apiPrefixUrl",
            "prefixUrl",
            "authorization",
            "headers",
            "clientRemoteType",
            "clientSafeConfig",
        }:
            continue
        hashed = dataflow_probe._alias(module_id, identifier)  # noqa: SLF001
        if hashed not in results:
            results.append(hashed)
    return results[:40]


def _value_summary(module_id: str, expression: str, imports: list[dict[str, str]]) -> dict[str, Any]:
    config_names = sorted(
        {
            name
            for name in (
                "customApiPrefixUrl",
                "customApiToken",
                "apiPrefixUrl",
                "prefixUrl",
                "authorization",
                "headers",
                "clientRemoteType",
                "clientSafeConfig",
            )
            if re.search(rf"\b{re.escape(name)}\b", expression)
        }
    )
    return {
        "kind": _safe_kind(expression),
        "config_properties": config_names,
        "source_refs": _source_refs(expression, imports),
        "alias_refs": _alias_refs(module_id, expression, imports),
    }


def _object_map(module_id: str, expression: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    value = expression.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return []
    results: list[dict[str, Any]] = []
    for part in contract_probe._split_top_level(value[1:-1]):  # noqa: SLF001
        fragment = part.strip()
        if not fragment or fragment.startswith("..."):
            continue
        colon = config_probe._find_top_level_colon(fragment)  # noqa: SLF001
        if colon is None:
            shorthand = fragment.strip()
            if _SAFE_KEY_RE.fullmatch(shorthand):
                results.append(
                    {
                        "key": _safe_key(shorthand),
                        "value": _value_summary(module_id, shorthand, imports),
                        "relation": "shorthand",
                    }
                )
            continue
        raw_key = fragment[:colon].strip()
        rhs = fragment[colon + 1 :].strip()
        results.append(
            {
                "key": _safe_key(raw_key),
                "value": _value_summary(module_id, rhs, imports),
                "relation": "property",
            }
        )
    return results[:400]


def _stage1_export_roles(body: str) -> list[dict[str, Any]]:
    exports = export_probe._all_named_exports(body)  # noqa: SLF001
    class_spans = export_probe._class_spans(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    for export in exports:
        symbol = export["symbol"].split(".")[-1]
        role = {
            "export_key": export["export_name"],
            "definition": "unresolved",
            "role_anchors": [],
        }
        for span in class_spans:
            if symbol not in {span.get("assigned_symbol"), span.get("class_name")}:
                continue
            fragment = body[span["start"] : span["end"]]
            role["definition"] = "class"
            role["role_anchors"] = [anchor for anchor in ROLE_ANCHORS if anchor in fragment]
            if span.get("extends"):
                # Preserve only whether an extends relation exists; the local base
                # identifier is not needed for the stage-one role decision.
                role["extends"] = True
            break
        if role["definition"] == "unresolved":
            # An export may be assigned to a class expression that the generic
            # span parser cannot bind. Associate only allowlisted anchors from a
            # small symbol-bounded assignment when possible, never the source.
            assign = re.search(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*class\b", body)
            if assign:
                brace = body.find("{", assign.start())
                end = contract_probe._find_matching(body, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
                if end is not None:
                    fragment = body[brace : end + 1]
                    role["definition"] = "class"
                    role["role_anchors"] = [anchor for anchor in ROLE_ANCHORS if anchor in fragment]
        results.append(role)
    return results[:80]


def _stage1_constructor_calls(composition_body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(composition_body)  # noqa: SLF001
    stage1_locals = [item["local"] for item in imports if item["source_module_id"] == STAGE1_MODULE_ID]
    results: list[dict[str, Any]] = []
    for local in stage1_locals:
        pattern = re.compile(rf"\bnew\s+{re.escape(local)}\.(?P<export>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
        for match in pattern.finditer(composition_body):
            open_paren = composition_body.find("(", match.start(), match.end())
            end = contract_probe._find_matching(composition_body, open_paren, "(", ")")  # noqa: SLF001
            if end is None:
                continue
            args = contract_probe._split_top_level(composition_body[open_paren + 1 : end])  # noqa: SLF001
            record: dict[str, Any] = {
                "source_module_id": STAGE1_MODULE_ID,
                "export_key": match.group("export"),
                "argument_count": len(args),
                "arguments": [_value_summary(COMPOSITION_MODULE_ID, arg, imports) for arg in args[:12]],
            }
            object_args = []
            for index, arg in enumerate(args[:12]):
                mapped = _object_map(COMPOSITION_MODULE_ID, arg, imports)
                if mapped:
                    object_args.append({"index": index, "properties": mapped})
            record["object_arguments"] = object_args
            results.append(record)
    return results[:40]


def analyze_modules(stage1_body: str, composition_body: str) -> dict[str, Any]:
    return {
        "stage1_module_id": STAGE1_MODULE_ID,
        "stage1_export_roles": _stage1_export_roles(stage1_body),
        "composition_module_id": COMPOSITION_MODULE_ID,
        "stage1_constructor_calls": _stage1_constructor_calls(composition_body),
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
    stage1_records: list[dict[str, Any]] = []
    composition_records: list[dict[str, Any]] = []

    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] == STAGE1_MODULE_ID:
                stage1_records.append(
                    {"member_path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest(), "body": module["body"]}
                )
            elif module["module_id"] == COMPOSITION_MODULE_ID:
                composition_records.append(
                    {"member_path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest(), "body": module["body"]}
                )

    analyses: list[dict[str, Any]] = []
    for stage1 in stage1_records:
        for composition in composition_records:
            analyses.append(
                {
                    "stage1_member_path": stage1["member_path"],
                    "stage1_member_sha256": stage1["member_sha256"],
                    "composition_member_path": composition["member_path"],
                    "composition_member_sha256": composition["member_sha256"],
                    **analyze_modules(stage1["body"], composition["body"]),
                }
            )

    return {
        "format": "musicark-yandex-upload-stage1-role-v1",
        "source": "asar-targeted-stage1-export-and-config-map",
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
    parser = argparse.ArgumentParser(description="Resolve Yandex upload stage-one export role and exact composition config map.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one role report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
