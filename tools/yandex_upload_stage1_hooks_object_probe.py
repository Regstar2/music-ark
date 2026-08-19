"""Resolve CommonJS/object forms of module 73202 property ``hooks``.

V42 located module 73202 in the official upload chunk but ruled out the common
webpack named-export/direct-export forms. This final static probe checks only
object-export forms such as ``module.exports = {hooks: ...}``, assignment of an
object to an export root, and ``Object.assign(...,{hooks: ...})``.

Only the stable property name ``hooks``, hashed local symbols, stable webpack
module/member refs, structural tokens, and allowlisted public Yandex URL
templates are emitted. Raw JavaScript, arbitrary strings, credentials, request
values, and raw identifiers are never emitted.
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
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_stage1_hooks_module_probe as hooks_module
import yandex_upload_stage1_prefix_use_site_probe as use_site_probe
import yandex_upload_target_probe as target_probe


MODULE_ID = "73202"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _object_hooks_rhs(expression: str) -> str | None:
    clean = expression.strip()
    if not (clean.startswith("{") and clean.endswith("}")):
        return None
    for part in contract_probe._split_top_level(clean[1:-1]):  # noqa: SLF001
        colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
        if colon is None:
            continue
        key = part[:colon].strip().strip("\"'")
        if key == "hooks":
            return part[colon + 1 :].strip()
    return None


def _candidate_rhs(body: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    # Any *.exports = { hooks: ... } or local = { hooks: ... } assignment.
    assign = re.compile(
        r"(?<![A-Za-z0-9_$])(?P<lhs>[A-Za-z_$][A-Za-z0-9_$]*(?:\.exports)?)\s*=\s*(?!=|>)"
    )
    for match in assign.finditer(body):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        value = _object_hooks_rhs(rhs) if rhs else None
        if value is not None:
            form = "module-exports-object" if match.group("lhs").endswith(".exports") else "object-assignment"
            item = {"form": form, "rhs": value}
            if item not in results:
                results.append(item)

    # Object.assign(target,{hooks: ...})
    for match in re.finditer(r"\bObject\.assign\s*\(", body):
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        for arg in args[1:]:
            value = _object_hooks_rhs(arg)
            if value is not None:
                item = {"form": "object-assign", "rhs": value}
                if item not in results:
                    results.append(item)

    return results[:40]


def _source_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(
            rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})"
        )
        members = list(member_pattern.finditer(expression))
        for found in members:
            record = {"source_module_id": item["source_module_id"], "export_key": found.group("member")}
            if record not in results:
                results.append(record)
        if not members and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _nearest_definition(body: str, identifier: str, before: int | None = None) -> tuple[int, str] | None:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        return None
    limit = len(body) if before is None else max(0, before)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)"
    )
    matches = [match for match in pattern.finditer(body, 0, limit)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return match.start(), rhs.strip()
    return None


def _trace(body: str, expression: str, imports: list[dict[str, str]], *, max_depth: int = 8) -> list[dict[str, Any]]:
    current = expression.strip()
    cursor: int | None = None
    seen: set[str] = set()
    chain: list[dict[str, Any]] = []
    for depth in range(max_depth + 1):
        record: dict[str, Any] = {
            "depth": depth,
            "kind": "identifier" if _IDENTIFIER_RE.fullmatch(current) else "expression",
            "sourceRefs": _source_refs(current, imports),
            "safeYandexTemplates": use_site_probe._safe_literals(current),  # noqa: SLF001
            "normalized": prefix_probe._normalized_expression(MODULE_ID, current, imports),  # noqa: SLF001
        }
        if _IDENTIFIER_RE.fullmatch(current):
            record["aliasHash"] = dataflow_probe._alias(MODULE_ID, current)  # noqa: SLF001
        chain.append(record)
        if not _IDENTIFIER_RE.fullmatch(current) or current in seen:
            break
        seen.add(current)
        assigned = _nearest_definition(body, current, cursor)
        if not assigned:
            break
        cursor, current = assigned
    return chain


def analyze_body(body: str) -> dict[str, Any]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    candidates = _candidate_rhs(body)
    return {
        "hooksObjectExportFound": bool(candidates),
        "candidates": [
            {
                "form": item["form"],
                "chain": _trace(body, item["rhs"], imports),
            }
            for item in candidates
        ],
    }


def build_report(path: Path, *, max_member_size: int = 16_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    occurrences: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for body in hooks_module._extract_target_bodies(text):  # noqa: SLF001
            occurrences.append(
                {
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "analysis": analyze_body(body),
                }
            )
    return {
        "format": "musicark-yandex-upload-stage1-hooks-object-v1",
        "source": "asar-targeted-commonjs-hooks-object-trace",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "occurrences": occurrences[:20],
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
    parser = argparse.ArgumentParser(description="Resolve CommonJS/object hooks export for stage-one module 73202.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized hooks object report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
