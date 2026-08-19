"""Source-free V9 probe for Yandex UGC upload webpack/module wiring.

The probe resolves webpack module boundaries, named exports, numeric module
imports, constructor uses, and relevant configuration bindings inside already
identified official app.asar members. It emits structural identifiers and
redacted expression kinds only. JavaScript source, ordinary string values,
credential values, header values, and network traffic are never emitted.
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
import yandex_upload_target_probe as target_probe


DEFAULT_ANCHORS = (
    "UgcUploadHttpClient",
    "BaseResourceHttpClient",
    "ResourceHttpClient",
    "getApiPrefixUrl",
    "customApiPrefixUrl",
    "customApiToken",
    "createHttpOptions",
    "createSessionRequestHeaders",
    "createRequestHeaders",
    "clientRemoteType",
    "clientSafeConfig",
    "getClientSafeConfig",
    "YandexMusicDesktopApp",
    "YandexMusicWebNext",
    "prefixUrl",
)

_INTERESTING_NAMES = set(DEFAULT_ANCHORS)
_MODULE_START_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<id>\d{1,8})\s*:\s*"
    r"(?:(?:function\s*\([^)]{0,200}\))|(?:\([^)]{0,200}\)\s*=>)|"
    r"(?:[A-Za-z_$][A-Za-z0-9_$]*\s*=>))\s*\{"
)
_IMPORT_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<local>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    r"(?P<loader>[A-Za-z_$][A-Za-z0-9_$]*)\(\s*(?P<module>\d{1,8})\s*\)"
)
_MEMBER_USE_RE = re.compile(
    r"(?P<base>[A-Za-z_$][A-Za-z0-9_$]*)\."
    r"(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)"
)
_CONSTRUCTOR_MEMBER_RE = re.compile(
    r"\bnew\s+(?P<base>[A-Za-z_$][A-Za-z0-9_$]*)\."
    r"(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)\s*\("
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


def _extract_modules(text: str) -> list[dict[str, Any]]:
    """Find top-level webpack module bodies without returning source text."""
    modules: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for match in _MODULE_START_RE.finditer(text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        brace = text.find("{", match.start(), match.end())
        if brace < 0:
            continue
        end = contract_probe._find_matching(text, brace, "{", "}")  # noqa: SLF001
        if end is None:
            continue
        occupied.append((match.start(), end + 1))
        modules.append(
            {
                "module_id": match.group("id"),
                "start": match.start(),
                "end": end + 1,
                "body": text[brace + 1 : end],
            }
        )
    return modules


def _imports(body: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in _IMPORT_RE.finditer(body):
        item = {"local": match.group("local"), "source_module_id": match.group("module")}
        if item not in results:
            results.append(item)
    return results[:200]


def _export_symbol(rhs: str) -> str | None:
    value = rhs.strip()
    for pattern in (_EXPORT_GETTER_RE, _EXPORT_FUNCTION_RE):
        match = pattern.match(value)
        if match:
            return match.group("symbol")
    return None


def _named_exports(body: str) -> list[dict[str, str]]:
    """Extract interesting names from webpack runtime .d(exports, {...}) calls."""
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
            name = part[:colon].strip().strip("\"'")
            if name not in _INTERESTING_NAMES:
                continue
            symbol = _export_symbol(part[colon + 1 :])
            if not symbol:
                continue
            item = {"name": name, "symbol": symbol}
            if item not in results:
                results.append(item)
    return results[:80]


def _member_uses(body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    results: list[dict[str, Any]] = []
    for match in _MEMBER_USE_RE.finditer(body):
        member = match.group("member")
        if member not in _INTERESTING_NAMES:
            continue
        base = match.group("base")
        item: dict[str, Any] = {"expression": f"{base}.{member}", "member": member}
        if base in import_map:
            item["source_module_id"] = import_map[base]
        if item not in results:
            results.append(item)
    return results[:160]


def _constructor_uses(body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    results: list[dict[str, Any]] = []
    for match in _CONSTRUCTOR_MEMBER_RE.finditer(body):
        member = match.group("member")
        if member not in _INTERESTING_NAMES:
            continue
        base = match.group("base")
        open_paren = body.find("(", match.start(), match.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
        args: list[str] = []
        if end is not None:
            args = contract_probe._split_top_level(body[open_paren + 1 : end])  # noqa: SLF001
        item: dict[str, Any] = {
            "callee": f"{base}.{member}",
            "export_name": member,
            "argument_kinds": [config_probe._expression_kind(arg) for arg in args[:12]],  # noqa: SLF001
        }
        if base in import_map:
            item["source_module_id"] = import_map[base]
        if item not in results:
            results.append(item)
    return results[:80]


def _class_relations(body: str, exports: list[dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for export in exports:
        symbol = export["symbol"].split(".")[-1]
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", symbol):
            continue
        patterns = (
            re.compile(
                rf"(?<![A-Za-z0-9_$]){re.escape(symbol)}\s*=\s*class"
                rf"(?:\s+[A-Za-z_$][A-Za-z0-9_$]*)?"
                rf"(?:\s+extends\s+(?P<base>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*))?\s*\{{"
            ),
            re.compile(
                rf"\bclass\s+{re.escape(symbol)}"
                rf"(?:\s+extends\s+(?P<base>[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*))?\s*\{{"
            ),
        )
        for pattern in patterns:
            match = pattern.search(body)
            if not match:
                continue
            relation: dict[str, Any] = {"export_name": export["name"], "symbol": symbol}
            if match.group("base"):
                relation["extends"] = match.group("base")
            brace = body.find("{", match.start(), match.end())
            class_end = (
                contract_probe._find_matching(body, brace, "{", "}")  # noqa: SLF001
                if brace >= 0
                else None
            )
            if class_end is not None:
                class_body = body[brace + 1 : class_end]
                ctor = re.search(r"\bconstructor\s*\((?P<params>[^)]{0,300})\)\s*\{", class_body)
                if ctor:
                    params = [
                        item.strip()
                        for item in contract_probe._split_top_level(ctor.group("params"))  # noqa: SLF001
                        if item.strip()
                    ]
                    relation["constructor_parameter_count"] = len(params)
                    ctor_brace = class_body.find("{", ctor.start(), ctor.end())
                    ctor_end = (
                        contract_probe._find_matching(class_body, ctor_brace, "{", "}")  # noqa: SLF001
                        if ctor_brace >= 0
                        else None
                    )
                    if ctor_end is not None:
                        ctor_body = class_body[ctor_brace + 1 : ctor_end]
                        bindings = config_probe._all_interesting_object_bindings(ctor_body)  # noqa: SLF001
                        if bindings:
                            relation["constructor_object_bindings"] = bindings[:80]
            results.append(relation)
            break
    return results[:40]


def _module_info(member_path: str, module: dict[str, Any], anchors: Iterable[str]) -> dict[str, Any]:
    body = module["body"]
    imports = _imports(body)
    exports = _named_exports(body)
    return {
        "member_path": member_path,
        "module_id": module["module_id"],
        "anchors_present": [anchor for anchor in anchors if re.search(re.escape(anchor), body, re.IGNORECASE)],
        "named_exports": exports,
        "imports": imports,
        "interesting_member_uses": _member_uses(body, imports),
        "constructor_uses": _constructor_uses(body, imports),
        "class_relations": _class_relations(body, exports),
        "object_bindings": config_probe._all_interesting_object_bindings(body),  # noqa: SLF001
        "call_relations": config_probe._call_relations(body),  # noqa: SLF001
    }


def _directly_interesting(info: dict[str, Any]) -> bool:
    return any(
        bool(info[key])
        for key in (
            "anchors_present",
            "named_exports",
            "interesting_member_uses",
            "constructor_uses",
            "class_relations",
            "object_bindings",
            "call_relations",
        )
    )


def _select_relevant_modules(infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available_ids = {info["module_id"] for info in infos}
    selected = {info["module_id"] for info in infos if _directly_interesting(info)}
    for _ in range(2):
        expanded = set(selected)
        for info in infos:
            if info["module_id"] in selected:
                expanded.update(
                    item["source_module_id"]
                    for item in info["imports"]
                    if item["source_module_id"] in available_ids
                )
            elif any(item["source_module_id"] in selected for item in info["imports"]):
                expanded.add(info["module_id"])
        if expanded == selected:
            break
        selected = expanded
    return [info for info in infos if info["module_id"] in selected]


def _resolved_edges(infos: list[dict[str, Any]]) -> list[dict[str, str]]:
    export_index = {
        (info["module_id"], export["name"])
        for info in infos
        for export in info["named_exports"]
    }
    edges: list[dict[str, str]] = []
    for info in infos:
        for use in info["interesting_member_uses"]:
            source = use.get("source_module_id")
            name = use.get("member")
            if source and name and (source, name) in export_index:
                item = {
                    "from_module_id": info["module_id"],
                    "to_module_id": source,
                    "export_name": name,
                    "relation": "imported-member-use",
                }
                if item not in edges:
                    edges.append(item)
        for use in info["constructor_uses"]:
            source = use.get("source_module_id")
            name = use.get("export_name")
            if source and name and (source, name) in export_index:
                item = {
                    "from_module_id": info["module_id"],
                    "to_module_id": source,
                    "export_name": name,
                    "relation": "constructor-use",
                }
                if item not in edges:
                    edges.append(item)
    return edges[:200]


def build_report(path: Path, offsets: Iterable[int], *, anchors: Iterable[str] = DEFAULT_ANCHORS) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    anchors_list = list(dict.fromkeys(str(value) for value in anchors if str(value)))
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

    all_infos: list[dict[str, Any]] = []
    member_summaries: list[dict[str, Any]] = []
    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        modules = _extract_modules(text)
        member_summaries.append(
            {
                **member,
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "webpack_modules_detected": len(modules),
            }
        )
        all_infos.extend(_module_info(member["path"], module, anchors_list) for module in modules)

    relevant = _select_relevant_modules(all_infos)
    return {
        "format": "musicark-yandex-upload-module-wiring-report-v1",
        "source": "asar-webpack-module-wiring-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "anchors": anchors_list,
        "members": member_summaries,
        "modules": relevant,
        "resolved_edges": _resolved_edges(relevant),
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
        description="Resolve source-free webpack/module wiring for the Yandex UGC upload HTTP client."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--anchor", action="append", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input, args.offset, anchors=args.anchor or DEFAULT_ANCHORS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V9 module-wiring report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
