"""Source-free V10 probe for cross-chunk UGC upload export/alias wiring.

V9 identified a concrete cross-chunk relationship between the upload-config
module and the module containing ``UgcUploadHttpClient`` but intentionally
filtered minified export names. V10 keeps the scope narrow: it resolves all safe
identifier-only export keys for modules containing the UGC anchor, then inspects
only modules that import those provider module IDs.

The report contains module IDs, identifier names, redacted expression kinds and
constructor/call relationships only. It never emits JavaScript source, ordinary
string values, credential/header values, cookies, authorization values, raw
ASAR contents, audio contents, or network traffic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yandex_upload_config_binding_probe as config_probe
import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


DEFAULT_ANCHOR = "UgcUploadHttpClient"
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,80}$")
_SAFE_MEMBER_RE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]{0,80}(?:\.[A-Za-z_$][A-Za-z0-9_$]{0,80})*$"
)
_SENSITIVE_NAME_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|signature|sign$)",
    re.IGNORECASE,
)
_EXPORT_GETTER_RE = re.compile(
    r"^(?:\(\)\s*=>|[A-Za-z_$][A-Za-z0-9_$]*\s*=>)\s*"
    r"(?P<symbol>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)$"
)
_EXPORT_FUNCTION_RE = re.compile(
    r"^function\s*\(\)\s*\{\s*return\s+"
    r"(?P<symbol>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)"
)


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def _safe_identifier(value: str) -> str | None:
    value = value.strip()
    if not _SAFE_IDENTIFIER_RE.fullmatch(value) or _SENSITIVE_NAME_RE.search(value):
        return None
    return value


def _safe_member(value: str) -> str | None:
    value = value.strip()
    if not _SAFE_MEMBER_RE.fullmatch(value):
        return None
    if any(_SENSITIVE_NAME_RE.search(part) for part in value.split(".")):
        return None
    return value


def _export_symbol(rhs: str) -> str | None:
    value = rhs.strip()
    for pattern in (_EXPORT_GETTER_RE, _EXPORT_FUNCTION_RE):
        match = pattern.match(value)
        if match:
            return _safe_member(match.group("symbol"))
    return None


def _all_named_exports(body: str) -> list[dict[str, str]]:
    """Return safe identifier-only webpack export mappings, including minified keys."""
    results: list[dict[str, str]] = []
    for match in re.finditer(r"\b[A-Za-z_$][A-Za-z0-9_$]*\.d\s*\(", body):
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        if len(args) < 2:
            continue
        export_map = args[1].strip()
        if not (export_map.startswith("{") and export_map.endswith("}")):
            continue
        for part in contract_probe._split_top_level(export_map[1:-1]):  # noqa: SLF001
            colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
            if colon is None:
                continue
            name = _safe_identifier(part[:colon].strip().strip("\"'"))
            symbol = _export_symbol(part[colon + 1 :])
            if not name or not symbol:
                continue
            item = {"export_name": name, "symbol": symbol}
            if item not in results:
                results.append(item)
    return results[:240]


def _class_spans(body: str) -> list[dict[str, Any]]:
    """Locate named/assigned class spans and expose only safe identifiers."""
    results: list[dict[str, Any]] = []
    patterns = (
        re.compile(
            r"(?<![A-Za-z0-9_$])(?P<assigned>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*class"
            r"(?:\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*))?"
            r"(?:\s+extends\s+(?P<base>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*))?\s*\{"
        ),
        re.compile(
            r"\bclass\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
            r"(?:\s+extends\s+(?P<base>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*))?\s*\{"
        ),
    )
    occupied: list[tuple[int, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(body):
            if any(start <= match.start() < end for start, end in occupied):
                continue
            brace = body.find("{", match.start(), match.end())
            end = contract_probe._find_matching(body, brace, "{", "}")  # noqa: SLF001
            if brace < 0 or end is None:
                continue
            assigned = _safe_identifier(match.groupdict().get("assigned") or "")
            name = _safe_identifier(match.groupdict().get("name") or "")
            base = _safe_member(match.groupdict().get("base") or "")
            occupied.append((match.start(), end + 1))
            results.append(
                {
                    "start": match.start(),
                    "end": end + 1,
                    "assigned_symbol": assigned,
                    "class_name": name,
                    "extends": base,
                }
            )
    return results


def _anchor_symbol_relations(body: str, anchor: str) -> list[dict[str, Any]]:
    """Map an anchor contained in a class span back to safe local symbols."""
    results: list[dict[str, Any]] = []
    for item in _class_spans(body):
        fragment = body[item["start"] : item["end"]]
        if anchor not in fragment:
            continue
        relation = {
            "anchor": anchor,
            "assigned_symbol": item.get("assigned_symbol"),
            "class_name": item.get("class_name"),
        }
        if item.get("extends"):
            relation["extends"] = item["extends"]
        if relation not in results:
            results.append(relation)

    # Direct named anchor may appear even when the class parser cannot associate
    # it with an assigned symbol. Preserve only that structural fact.
    if re.search(rf"\bclass\s+{re.escape(anchor)}\b", body):
        direct = {"anchor": anchor, "class_name": anchor, "assigned_symbol": None}
        if direct not in results:
            results.append(direct)
    return results[:40]


def _relation_for_use(body: str, start: int, end: int) -> str:
    left = body[max(0, start - 24) : start]
    right = body[end : min(len(body), end + 12)]
    if re.search(r"\bnew\s*$", left):
        return "constructor"
    if re.search(r"\bextends\s*$", left):
        return "extends"
    if re.match(r"\s*\(", right):
        return "call"
    return "member-use"


def _alias_member_uses(body: str, alias: str, source_module_id: str) -> list[dict[str, Any]]:
    """Inspect every safe member use on one proven webpack import alias."""
    if not _SAFE_IDENTIFIER_RE.fullmatch(alias):
        return []
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(alias)}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,80}})")
    results: list[dict[str, Any]] = []
    for match in pattern.finditer(body):
        member = _safe_identifier(match.group("member"))
        if not member:
            continue
        relation = _relation_for_use(body, match.start(), match.end())
        item: dict[str, Any] = {
            "source_module_id": source_module_id,
            "import_alias": alias,
            "member": member,
            "relation": relation,
        }
        if relation in {"constructor", "call"}:
            open_paren = body.find("(", match.end())
            if open_paren >= 0:
                close = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
                if close is not None:
                    args = contract_probe._split_top_level(body[open_paren + 1 : close])  # noqa: SLF001
                    item["argument_kinds"] = [
                        config_probe._expression_kind(arg) for arg in args[:12]  # noqa: SLF001
                    ]
        if item not in results:
            results.append(item)
    return results[:160]


def _module_record(member_path: str, module: dict[str, Any], anchor: str) -> dict[str, Any]:
    body = module["body"]
    imports = wiring_probe._imports(body)  # noqa: SLF001
    return {
        "member_path": member_path,
        "module_id": module["module_id"],
        "anchor_present": anchor in body,
        "exports": _all_named_exports(body),
        "anchor_symbol_relations": _anchor_symbol_relations(body, anchor),
        "imports": imports,
        "object_bindings": config_probe._all_interesting_object_bindings(body),  # noqa: SLF001
    }


def _anchor_symbols(provider: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for relation in provider["anchor_symbol_relations"]:
        for key in ("assigned_symbol", "class_name"):
            value = relation.get(key)
            if isinstance(value, str) and value:
                symbols.add(value)
    return symbols


def _resolved_export_names(provider: dict[str, Any]) -> set[str]:
    anchor_symbols = _anchor_symbols(provider)
    results: set[str] = set()
    for export in provider["exports"]:
        symbol_root = export["symbol"].split(".")[-1]
        if export["symbol"] in anchor_symbols or symbol_root in anchor_symbols:
            results.add(export["export_name"])
    return results


def build_report(path: Path, offsets: Iterable[int], *, anchor: str = DEFAULT_ANCHOR) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    data_start, mappings = target_probe.locate_members(path, offsets_list)

    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(
                key,
                {
                    "path": member["path"],
                    "size": member["size"],
                    "absolute_start": member["absolute_start"],
                    "triggering_offsets": [],
                },
            )
            item["triggering_offsets"].append(mapping["offset"])

    records: list[dict[str, Any]] = []
    member_summaries: list[dict[str, Any]] = []
    raw_modules: list[tuple[str, dict[str, Any]]] = []
    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        modules = wiring_probe._extract_modules(text)  # noqa: SLF001
        member_summaries.append(
            {
                **member,
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "webpack_modules_detected": len(modules),
            }
        )
        for module in modules:
            raw_modules.append((member["path"], module))
            records.append(_module_record(member["path"], module, anchor))

    providers = [record for record in records if record["anchor_present"]]
    provider_ids = {record["module_id"] for record in providers}

    importers: list[dict[str, Any]] = []
    for member_path, module in raw_modules:
        imports = wiring_probe._imports(module["body"])  # noqa: SLF001
        relevant_imports = [item for item in imports if item["source_module_id"] in provider_ids]
        if not relevant_imports:
            continue
        uses: list[dict[str, Any]] = []
        for imported in relevant_imports:
            uses.extend(
                _alias_member_uses(
                    module["body"],
                    imported["local"],
                    imported["source_module_id"],
                )
            )
        importers.append(
            {
                "member_path": member_path,
                "module_id": module["module_id"],
                "provider_imports": relevant_imports,
                "provider_alias_uses": uses,
                "object_bindings": config_probe._all_interesting_object_bindings(module["body"]),  # noqa: SLF001
            }
        )

    resolved_edges: list[dict[str, str]] = []
    for provider in providers:
        resolved_exports = _resolved_export_names(provider)
        if not resolved_exports:
            continue
        for importer in importers:
            for use in importer["provider_alias_uses"]:
                if use["source_module_id"] != provider["module_id"]:
                    continue
                if use["member"] not in resolved_exports:
                    continue
                edge = {
                    "from_module_id": importer["module_id"],
                    "to_module_id": provider["module_id"],
                    "export_name": use["member"],
                    "relation": use["relation"],
                }
                if edge not in resolved_edges:
                    resolved_edges.append(edge)

    return {
        "format": "musicark-yandex-upload-export-alias-report-v1",
        "source": "asar-cross-chunk-export-alias-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "anchor": anchor,
        "members": member_summaries,
        "providers": providers,
        "importers": importers,
        "resolved_edges": resolved_edges,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "ordinary_string_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve minified cross-chunk export aliases for the Yandex UGC upload client."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--anchor", default=DEFAULT_ANCHOR)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input, args.offset, anchor=args.anchor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V10 export-alias report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
