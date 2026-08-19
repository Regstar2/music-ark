"""Trace upload client construction inside the proven webpack composition root.

V18 established module 7644 as the composition root that imports the upload
resource (12690), request/session header layer (37558) and UGC HTTP provider
(70204), while also containing customApiPrefixUrl/customApiToken/prefixUrl/
authorization properties.

This probe inspects only that module and emits structural call/config relations.
Webpack source-module IDs and export keys may be emitted; local/minified variable
identifiers and scalar string values are replaced with deterministic hashes or
structural kinds. No network I/O is performed.
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
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
SOURCE_MODULE_IDS = {"12690", "31322", "37558", "70204", "10894", "32732"}
CONFIG_PROPERTIES = {
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "prefixUrl",
    "authorization",
    "headers",
    "clientRemoteType",
    "clientSafeConfig",
}
_JS_KEYWORDS = dataflow_probe._JS_KEYWORDS  # noqa: SLF001
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
_MEMBER_RE_TEMPLATE = r"(?P<new>\bnew\s+)?{base}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)\s*\("
_BARE_MEMBER_RE_TEMPLATE = r"{base}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)"


def _hash_local(module_id: str, value: str) -> str:
    return dataflow_probe._alias(module_id, value)  # noqa: SLF001


def _target_properties(expression: str) -> list[str]:
    return sorted({name for name in CONFIG_PROPERTIES if re.search(rf"\b{re.escape(name)}\b", expression)})


def _alias_refs(module_id: str, expression: str, *, excluded: set[str]) -> list[str]:
    refs: list[str] = []
    for identifier in _IDENTIFIER_RE.findall(expression):
        if identifier in CONFIG_PROPERTIES or identifier in _JS_KEYWORDS or identifier in excluded:
            continue
        hashed = _hash_local(module_id, identifier)
        if hashed not in refs:
            refs.append(hashed)
    return refs[:40]


def _expression_summary(
    module_id: str,
    expression: str,
    *,
    import_locals: set[str],
    import_map: dict[str, str],
) -> dict[str, Any]:
    source_refs: list[dict[str, str]] = []
    for local, source_id in import_map.items():
        if not re.search(rf"\b{re.escape(local)}\b", expression):
            continue
        item = {"source_module_id": source_id}
        if item not in source_refs:
            source_refs.append(item)
    return {
        "kind": config_probe._expression_kind(expression),  # noqa: SLF001
        "config_properties": _target_properties(expression),
        "source_module_refs": source_refs,
        "alias_refs": _alias_refs(module_id, expression, excluded=import_locals),
    }


def _config_paths_for_aliases(
    graph: dict[str, set[str]],
    aliases: list[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for prop in sorted(CONFIG_PROPERTIES):
        for alias in aliases:
            path = dataflow_probe._shortest_path(graph, prop, alias, max_edges=5)  # noqa: SLF001
            if not path:
                continue
            item = {"property": prop, "argument_alias": alias, "path": path}
            if item not in results:
                results.append(item)
    return results[:80]


def _call_uses(module_id: str, body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    import_locals = set(import_map)
    graph = dataflow_probe.build_local_graph(module_id, dataflow_probe.tokenize(body))
    results: list[dict[str, Any]] = []

    for local, source_id in import_map.items():
        if source_id not in SOURCE_MODULE_IDS:
            continue
        pattern = re.compile(_MEMBER_RE_TEMPLATE.format(base=re.escape(local)))
        for match in pattern.finditer(body):
            open_paren = body.find("(", match.start(), match.end())
            end = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
            if end is None:
                continue
            args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
            arg_summaries = [
                _expression_summary(
                    module_id,
                    arg,
                    import_locals=import_locals,
                    import_map=import_map,
                )
                for arg in args[:16]
            ]
            alias_refs = [alias for summary in arg_summaries for alias in summary["alias_refs"]]
            item = {
                "source_module_id": source_id,
                "export_key": match.group("member"),
                "relation": "constructor" if match.group("new") else "call",
                "argument_count": len(args),
                "arguments": arg_summaries,
                "config_paths_to_arguments": _config_paths_for_aliases(graph, alias_refs),
            }
            if item not in results:
                results.append(item)

    return results[:300]


def _bare_member_uses(body: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        if item["source_module_id"] not in SOURCE_MODULE_IDS:
            continue
        pattern = re.compile(_BARE_MEMBER_RE_TEMPLATE.format(base=re.escape(item["local"])))
        for match in pattern.finditer(body):
            record = {
                "source_module_id": item["source_module_id"],
                "export_key": match.group("member"),
            }
            if record not in results:
                results.append(record)
    return results[:300]


def _binding_summaries(module_id: str, body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    import_locals = set(import_map)
    results: list[dict[str, Any]] = []
    for binding in config_probe._all_interesting_object_bindings(body):  # noqa: SLF001
        key = str(binding.get("key") or "")
        if key not in CONFIG_PROPERTIES:
            continue
        expression = str(binding.get("expression") or "")
        result = {
            "key": key,
            "value_kind": binding.get("value_kind") or config_probe._expression_kind(expression),  # noqa: SLF001
        }
        # Older helper versions may expose a structural expression label rather
        # than raw source. Re-summarize only if an expression is present.
        if expression:
            result["value"] = _expression_summary(
                module_id,
                expression,
                import_locals=import_locals,
                import_map=import_map,
            )
        if result not in results:
            results.append(result)
    return results[:120]


def analyze_module(body: str) -> dict[str, Any]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    selected_imports = [
        {"source_module_id": item["source_module_id"]}
        for item in imports
        if item["source_module_id"] in SOURCE_MODULE_IDS
    ]
    return {
        "module_id": COMPOSITION_MODULE_ID,
        "selected_imports": selected_imports,
        "config_properties_present": sorted({name for name in CONFIG_PROPERTIES if name in body}),
        "imported_member_uses": _bare_member_uses(body, imports),
        "imported_calls": _call_uses(COMPOSITION_MODULE_ID, body, imports),
        "config_bindings": _binding_summaries(COMPOSITION_MODULE_ID, body, imports),
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
    matches: list[dict[str, Any]] = []

    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] != COMPOSITION_MODULE_ID:
                continue
            matches.append(
                {
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    **analyze_module(module["body"]),
                }
            )

    return {
        "format": "musicark-yandex-upload-runtime-composition-v1",
        "source": "asar-targeted-composition-root-structural-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "composition_module_id": COMPOSITION_MODULE_ID,
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
    parser = argparse.ArgumentParser(description="Trace upload client construction inside webpack module 7644.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime composition report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
