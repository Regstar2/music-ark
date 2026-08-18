"""Source-free V11 probe for the two resolved UGC provider export keys.

V10 reduced the upload-config -> provider relationship to module 39670 importing
module 70204 and using only export keys Xc and RG. V11 determines the structural
role of those two exports without emitting JavaScript source, ordinary strings,
credential/header values, raw ASAR bytes, or network traffic.
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
import yandex_upload_export_alias_probe as alias_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


DEFAULT_PROVIDER_MODULE = "70204"
DEFAULT_IMPORTER_MODULE = "39670"
DEFAULT_EXPORTS = ("Xc", "RG")
ROLE_ANCHORS = (
    "UgcUploadHttpClient",
    "BaseResourceHttpClient",
    "ResourceHttpClient",
    "loader/upload-url",
    "getUploadUrl",
    "uploadFile",
    "createHttpOptions",
    "prefixUrl",
    "excludeHeaders",
    "withoutHeaders",
)
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,80}$")
_ASSIGNMENT_RE_TEMPLATE = r"(?<![A-Za-z0-9_$]){symbol}\s*=\s*"
_IMPORT_MEMBER_ASSIGN_RE_TEMPLATE = (
    r"(?<![A-Za-z0-9_$]){symbol}\s*=\s*"
    r"(?P<base>[A-Za-z_$][A-Za-z0-9_$]*)\."
    r"(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,80}})"
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
    return value if _SAFE_IDENTIFIER_RE.fullmatch(value) else None


def _definition_shapes(body: str, symbol: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Classify safe definition forms for one local symbol."""
    if not _safe_identifier(symbol):
        return []
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    results: list[dict[str, Any]] = []

    patterns: list[tuple[str, re.Pattern[str]]] = [
        ("class-assignment", re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*class\b")),
        ("named-class", re.compile(rf"\bclass\s+{re.escape(symbol)}\b")),
        ("function-assignment", re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*function\b")),
        ("named-function", re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\(")),
        ("arrow-assignment", re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>")),
    ]
    for kind, pattern in patterns:
        if pattern.search(body):
            item = {"kind": kind}
            if item not in results:
                results.append(item)

    import_pattern = re.compile(
        _IMPORT_MEMBER_ASSIGN_RE_TEMPLATE.format(symbol=re.escape(symbol))
    )
    for match in import_pattern.finditer(body):
        base = match.group("base")
        member = _safe_identifier(match.group("member"))
        item: dict[str, Any] = {"kind": "import-member-assignment", "member": member}
        if base in import_map:
            item["source_module_id"] = import_map[base]
        if item not in results:
            results.append(item)

    assignment_pattern = re.compile(_ASSIGNMENT_RE_TEMPLATE.format(symbol=re.escape(symbol)))
    for match in assignment_pattern.finditer(body):
        rhs_start = match.end()
        rhs = body[rhs_start : min(len(body), rhs_start + 240)].lstrip()
        if not rhs:
            continue
        if rhs.startswith("class") or rhs.startswith("function"):
            continue
        call_match = re.match(r"(?:new\s+)?([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)\s*\(", rhs)
        if call_match:
            item = {"kind": "call-assignment", "callee": call_match.group(1)}
            if item not in results:
                results.append(item)
        elif re.match(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+", rhs):
            member_match = re.match(r"([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+)", rhs)
            if member_match:
                item = {"kind": "member-assignment", "value": member_match.group(1)}
                if item not in results:
                    results.append(item)
    return results[:40]


def _symbol_region(body: str, symbol: str) -> tuple[int, int] | None:
    """Find the smallest class/function/assignment expression region for a symbol."""
    if not _safe_identifier(symbol):
        return None
    candidates: list[tuple[int, int]] = []

    class_patterns = (
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*class(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?(?:\s+extends\s+[A-Za-z_$][A-Za-z0-9_$.]*)?\s*\{{"),
        re.compile(rf"\bclass\s+{re.escape(symbol)}(?:\s+extends\s+[A-Za-z_$][A-Za-z0-9_$.]*)?\s*\{{"),
    )
    for pattern in class_patterns:
        for match in pattern.finditer(body):
            brace = body.find("{", match.start(), match.end())
            end = contract_probe._find_matching(body, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
            if end is not None:
                candidates.append((match.start(), end + 1))

    func_patterns = (
        re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*function(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?\s*\([^)]*\)\s*\{{"),
        re.compile(rf"\bfunction\s+{re.escape(symbol)}\s*\([^)]*\)\s*\{{"),
    )
    for pattern in func_patterns:
        for match in pattern.finditer(body):
            brace = body.find("{", match.start(), match.end())
            end = contract_probe._find_matching(body, brace, "{", "}") if brace >= 0 else None  # noqa: SLF001
            if end is not None:
                candidates.append((match.start(), end + 1))

    if not candidates:
        assignment = re.search(_ASSIGNMENT_RE_TEMPLATE.format(symbol=re.escape(symbol)), body)
        if assignment:
            semicolon = body.find(";", assignment.end())
            end = semicolon + 1 if semicolon >= 0 else min(len(body), assignment.end() + 600)
            candidates.append((assignment.start(), end))

    if not candidates:
        return None
    return min(candidates, key=lambda item: item[1] - item[0])


def _role_anchors(body: str, symbol: str) -> list[str]:
    region = _symbol_region(body, symbol)
    if region is None:
        return []
    fragment = body[region[0] : region[1]]
    return [anchor for anchor in ROLE_ANCHORS if anchor in fragment]


def _provider_export_roles(body: str, export_names: Iterable[str]) -> list[dict[str, Any]]:
    exports = alias_probe._all_named_exports(body)  # noqa: SLF001
    imports = wiring_probe._imports(body)  # noqa: SLF001
    by_name = {item["export_name"]: item["symbol"] for item in exports}
    results: list[dict[str, Any]] = []
    for export_name in export_names:
        symbol = by_name.get(export_name)
        if not symbol:
            continue
        root = symbol.split(".")[-1]
        results.append(
            {
                "export_name": export_name,
                "symbol": symbol,
                "definition_shapes": _definition_shapes(body, root, imports),
                "role_anchors": _role_anchors(body, root),
            }
        )
    return results


def _importer_use_context(body: str, alias: str, member: str) -> list[dict[str, Any]]:
    """Classify importer use without emitting source context."""
    if not _safe_identifier(alias) or not _safe_identifier(member):
        return []
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(alias)}\.{re.escape(member)}")
    results: list[dict[str, Any]] = []
    for match in pattern.finditer(body):
        left = body[max(0, match.start() - 120) : match.start()]
        right = body[match.end() : min(len(body), match.end() + 160)]
        relation = alias_probe._relation_for_use(body, match.start(), match.end())  # noqa: SLF001
        item: dict[str, Any] = {"relation": relation}

        key_match = re.search(r"([A-Za-z_$][A-Za-z0-9_$-]{0,80})\s*:\s*$", left)
        if key_match:
            key = _safe_identifier(key_match.group(1).replace("-", ""))
            if key:
                item["object_property_shape"] = "identifier-key"

        if re.match(r"\s*\)", right):
            item["argument_position_use"] = True
        if re.search(r"(?:=|:)\s*$", left):
            item["value_position_use"] = True
        if re.match(r"\s*\.", right):
            item["chained_member_use"] = True
        if item not in results:
            results.append(item)
    return results[:40]


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    provider_module_id: str = DEFAULT_PROVIDER_MODULE,
    importer_module_id: str = DEFAULT_IMPORTER_MODULE,
    export_names: Iterable[str] = DEFAULT_EXPORTS,
) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    export_list = list(dict.fromkeys(str(value) for value in export_names if _safe_identifier(str(value))))
    data_start, mappings = target_probe.locate_members(path, offsets_list)

    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(key, {**member, "triggering_offsets": []})
            item["triggering_offsets"].append(mapping["offset"])

    member_summaries: list[dict[str, Any]] = []
    provider_records: list[dict[str, Any]] = []
    importer_records: list[dict[str, Any]] = []

    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        modules = wiring_probe._extract_modules(text)  # noqa: SLF001
        member_summaries.append(
            {
                "path": member["path"],
                "size": member["size"],
                "absolute_start": member["absolute_start"],
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "webpack_modules_detected": len(modules),
            }
        )
        for module in modules:
            if module["module_id"] == provider_module_id:
                provider_records.append(
                    {
                        "member_path": member["path"],
                        "module_id": provider_module_id,
                        "export_roles": _provider_export_roles(module["body"], export_list),
                    }
                )
            if module["module_id"] == importer_module_id:
                imports = wiring_probe._imports(module["body"])  # noqa: SLF001
                aliases = [item["local"] for item in imports if item["source_module_id"] == provider_module_id]
                uses: list[dict[str, Any]] = []
                for alias in aliases:
                    for export_name in export_list:
                        uses.append(
                            {
                                "import_alias": alias,
                                "export_name": export_name,
                                "contexts": _importer_use_context(module["body"], alias, export_name),
                            }
                        )
                importer_records.append(
                    {
                        "member_path": member["path"],
                        "module_id": importer_module_id,
                        "provider_aliases": aliases,
                        "uses": uses,
                        "object_bindings": config_probe._all_interesting_object_bindings(module["body"]),  # noqa: SLF001
                    }
                )

    return {
        "format": "musicark-yandex-upload-symbol-role-report-v1",
        "source": "asar-targeted-export-role-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "provider_module_id": provider_module_id,
        "importer_module_id": importer_module_id,
        "export_names": export_list,
        "members": member_summaries,
        "providers": provider_records,
        "importers": importer_records,
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
    parser = argparse.ArgumentParser(description="Resolve structural roles of Xc/RG in Yandex UGC provider module 70204.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--provider-module", default=DEFAULT_PROVIDER_MODULE)
    parser.add_argument("--importer-module", default=DEFAULT_IMPORTER_MODULE)
    parser.add_argument("--export", action="append", dest="exports", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(
        args.input,
        args.offset,
        provider_module_id=str(args.provider_module),
        importer_module_id=str(args.importer_module),
        export_names=args.exports or DEFAULT_EXPORTS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V11 symbol-role report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
