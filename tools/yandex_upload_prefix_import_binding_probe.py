"""Resolve full import bindings used by the upload stage-one prefix expression.

The legacy webpack import parser records ``x=require(32732).pp...`` as only
``x -> module 32732``. That is sufficient for topology, but it loses named-export
or method chains and can make a derived string look like a module namespace.

This probe inspects only imports referenced by the exact V21 stage-one prefix RHS
and emits the complete *normalized* assignment RHS: numeric module IDs, stable
export/member names directly attached to webpack require results, operators,
hashed local aliases and structural string/number kinds. Raw local identifiers,
arbitrary strings and source contexts are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
TARGET_SOURCE_MODULES = {"32732", "91953", "12690", "70204"}
_IMPORT_BINDING_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<local>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    r"(?P<loader>[A-Za-z_$][A-Za-z0-9_$]*)\(\s*(?P<module>\d{1,8})\s*\)"
)
_SAFE_MEMBER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")


def _hash(value: str) -> str:
    return dataflow_probe._alias(COMPOSITION_MODULE_ID, value)  # noqa: SLF001


def _full_assignment_rhs(body: str, local: str) -> str | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(local)}\s*=\s*(?!=|>)")
    for match in pattern.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return rhs
    return None


def _require_chain(expression: str, loader: str, module_id: str) -> list[str]:
    """Return stable members immediately chained from one require(module) call."""
    pattern = re.compile(rf"\b{re.escape(loader)}\(\s*{re.escape(module_id)}\s*\)(?P<tail>(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)")
    match = pattern.search(expression)
    if not match:
        return []
    tail = match.group("tail") or ""
    return [part for part in tail.split(".") if part and _SAFE_MEMBER_RE.fullmatch(part)][:20]


def _normalized_binding(expression: str, imports: list[dict[str, str]]) -> list[str]:
    return prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, expression, imports)  # noqa: SLF001


def analyze_composition(body: str) -> dict[str, Any]:
    prefix_rhs, imports = prefix_probe._stage1_prefix_expression(body)  # noqa: SLF001
    if prefix_rhs is None:
        return {"module_id": COMPOSITION_MODULE_ID, "stage1PrefixFound": False, "bindings": []}

    referenced_import_locals = {
        item["local"]
        for item in imports
        if re.search(rf"\b{re.escape(item['local'])}\b", prefix_rhs)
    }
    import_meta = {item["local"]: item["source_module_id"] for item in imports}
    binding_matches = {
        match.group("local"): {
            "loader": match.group("loader"),
            "source_module_id": match.group("module"),
        }
        for match in _IMPORT_BINDING_RE.finditer(body)
    }

    results: list[dict[str, Any]] = []
    for local in sorted(referenced_import_locals):
        source_id = import_meta.get(local)
        if source_id not in TARGET_SOURCE_MODULES:
            continue
        rhs = _full_assignment_rhs(body, local)
        match = binding_matches.get(local, {})
        record: dict[str, Any] = {
            "binding_alias": _hash(local),
            "source_module_id": source_id,
            "definitionFound": rhs is not None,
        }
        if rhs is not None:
            record["normalizedRhs"] = _normalized_binding(rhs, imports)
            loader = str(match.get("loader") or "")
            if loader:
                record["requireMemberChain"] = _require_chain(rhs, loader, source_id)
        results.append(record)

    return {
        "module_id": COMPOSITION_MODULE_ID,
        "stage1PrefixFound": True,
        "normalizedStage1Prefix": _normalized_binding(prefix_rhs, imports),
        "bindings": results,
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
                    **analyze_composition(module["body"]),
                }
            )
    return {
        "format": "musicark-yandex-upload-prefix-import-binding-v1",
        "source": "asar-exact-stage1-prefix-import-binding-scan",
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
    parser = argparse.ArgumentParser(description="Resolve exact webpack import bindings used by the upload stage-one prefix.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one prefix import-binding report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
