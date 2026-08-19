"""Source-free V12 graph probe for resolving the Yandex UGC client export.

V11 established that module 39670 uses only provider exports Xc and RG from
module 70204, but its direct definition parser could not resolve the local
minified symbols. V12 builds a narrow identifier graph inside module 70204 and
reports only safe identifier paths to allowlisted upload protocol anchors.

No JavaScript source, ordinary string values, credentials, header values, raw
ASAR bytes, audio bytes, or network traffic are emitted.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yandex_upload_export_alias_probe as alias_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


DEFAULT_PROVIDER_MODULE = "70204"
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
_IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]{0,80}")
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature|sign$)",
    re.IGNORECASE,
)
_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_$])(?P<lhs>[A-Za-z_$][A-Za-z0-9_$]{0,80})\s*=\s*(?!=|>)"
)
_NAMED_CLASS_RE = re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]{0,80})[^\{]*\{")
_NAMED_FUNCTION_RE = re.compile(r"\bfunction\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]{0,80})\s*\([^)]*\)\s*\{")


def _safe_identifier(value: str) -> str | None:
    value = value.strip()
    if not _SAFE_IDENTIFIER_RE.fullmatch(value) or _SENSITIVE_RE.search(value):
        return None
    return value


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def _scan_expression_end(body: str, start: int, *, max_chars: int = 12000) -> int:
    """Return the end of one minified assignment expression without exposing it."""
    paren = bracket = brace = 0
    quote: str | None = None
    escaped = False
    i = start
    limit = min(len(body), start + max_chars)
    while i < limit:
        ch = body[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in {'"', "'", "`"}:
            quote = ch
            i += 1
            continue
        if ch == "(" :
            paren += 1
        elif ch == ")" and paren:
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]" and bracket:
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}" and brace:
            brace -= 1
        elif ch in {",", ";"} and paren == bracket == brace == 0:
            return i
        i += 1
    return limit


def _find_matching_brace(body: str, open_index: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for i in range(open_index, len(body)):
        ch = body[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in {'"', "'", "`"}:
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _rhs_kind(rhs: str) -> str:
    value = rhs.lstrip()
    if value.startswith("class"):
        return "class-expression"
    if value.startswith("function"):
        return "function-expression"
    if value.startswith("new "):
        return "new-expression"
    if value.startswith("{"):
        return "object-expression"
    if value.startswith("["):
        return "array-expression"
    if "=>" in value[:240]:
        return "arrow-expression"
    if re.match(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\s*\(", value):
        return "call-expression"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", value):
        return "identifier-reference"
    return "other-expression"


def _safe_identifiers(fragment: str, *, limit: int = 40) -> list[str]:
    results: list[str] = []
    for match in _IDENTIFIER_RE.finditer(fragment):
        value = _safe_identifier(match.group(0))
        if not value or value in {"class", "function", "return", "new", "this", "const", "let", "var", "true", "false", "null", "undefined"}:
            continue
        if value not in results:
            results.append(value)
        if len(results) >= limit:
            break
    return results


def _assignment_records(body: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for match in _ASSIGNMENT_RE.finditer(body):
        lhs = _safe_identifier(match.group("lhs"))
        if not lhs:
            continue
        end = _scan_expression_end(body, match.end())
        rhs = body[match.end():end]
        identifiers = [item for item in _safe_identifiers(rhs) if item != lhs]
        anchors = [anchor for anchor in ROLE_ANCHORS if anchor in rhs]
        records.append(
            {
                "owner": lhs,
                "kind": _rhs_kind(rhs),
                "references": identifiers,
                "anchors": anchors,
            }
        )
    return records[:4000]


def _named_region_records(body: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for kind, pattern in (("named-class", _NAMED_CLASS_RE), ("named-function", _NAMED_FUNCTION_RE)):
        for match in pattern.finditer(body):
            owner = _safe_identifier(match.group("name"))
            if not owner:
                continue
            open_index = body.find("{", match.start(), match.end())
            end = _find_matching_brace(body, open_index) if open_index >= 0 else None
            if end is None:
                continue
            fragment = body[match.start():end + 1]
            references = [item for item in _safe_identifiers(fragment) if item != owner]
            anchors = [anchor for anchor in ROLE_ANCHORS if anchor in fragment]
            records.append(
                {
                    "owner": owner,
                    "kind": kind,
                    "references": references,
                    "anchors": anchors,
                }
            )
    return records[:1000]


def _graph(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    owners = {record["owner"] for record in records}
    for record in records:
        owner = record["owner"]
        graph.setdefault(owner, set())
        for ref in record["references"]:
            if ref not in owners:
                continue
            graph.setdefault(ref, set())
            graph[owner].add(ref)
            graph[ref].add(owner)
    return graph


def _shortest_path(graph: dict[str, set[str]], start: str, targets: set[str], *, max_depth: int = 8) -> list[str] | None:
    if start in targets:
        return [start]
    queue: deque[list[str]] = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for nxt in sorted(graph.get(path[-1], set())):
            if nxt in seen:
                continue
            new_path = [*path, nxt]
            if nxt in targets:
                return new_path
            seen.add(nxt)
            queue.append(new_path)
    return None


def _provider_record(member_path: str, body: str, export_names: Iterable[str]) -> dict[str, Any]:
    exports = alias_probe._all_named_exports(body)  # noqa: SLF001
    by_name = {item["export_name"]: item["symbol"] for item in exports}
    records = _assignment_records(body) + _named_region_records(body)
    anchor_records = [record for record in records if record["anchors"]]
    targets = {record["owner"] for record in anchor_records}
    graph = _graph(records)

    export_paths: list[dict[str, Any]] = []
    for export_name in export_names:
        symbol = by_name.get(export_name)
        if not symbol:
            continue
        root = _safe_identifier(symbol.split(".")[-1])
        if not root:
            continue
        path = _shortest_path(graph, root, targets)
        target = path[-1] if path else None
        target_anchors: list[str] = []
        target_kind: str | None = None
        if target:
            for record in anchor_records:
                if record["owner"] == target:
                    target_anchors = list(dict.fromkeys([*target_anchors, *record["anchors"]]))
                    target_kind = target_kind or record["kind"]
        export_paths.append(
            {
                "export_name": export_name,
                "symbol": symbol,
                "path": path or [],
                "target_kind": target_kind,
                "target_anchors": target_anchors,
            }
        )

    return {
        "member_path": member_path,
        "module_id": DEFAULT_PROVIDER_MODULE,
        "export_paths": export_paths,
        "anchor_owners": [
            {
                "owner": record["owner"],
                "kind": record["kind"],
                "anchors": record["anchors"],
            }
            for record in anchor_records[:120]
        ],
        "assignment_count": len(records),
        "graph_node_count": len(graph),
    }


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    provider_module_id: str = DEFAULT_PROVIDER_MODULE,
    export_names: Iterable[str] = DEFAULT_EXPORTS,
) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    data_start, mappings = target_probe.locate_members(path, offsets_list)
    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(key, {**member, "triggering_offsets": []})
            item["triggering_offsets"].append(mapping["offset"])

    member_summaries: list[dict[str, Any]] = []
    providers: list[dict[str, Any]] = []
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
            if module["module_id"] != provider_module_id:
                continue
            record = _provider_record(member["path"], module["body"], export_names)
            record["module_id"] = provider_module_id
            providers.append(record)

    return {
        "format": "musicark-yandex-upload-symbol-graph-report-v1",
        "source": "asar-targeted-symbol-graph-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "provider_module_id": provider_module_id,
        "export_names": list(export_names),
        "members": member_summaries,
        "providers": providers,
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
    parser = argparse.ArgumentParser(description="Resolve Xc/RG through a source-free provider symbol graph.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--offset", type=int, action="append", required=True)
    parser.add_argument("--provider-module", default=DEFAULT_PROVIDER_MODULE)
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
        export_names=args.exports or DEFAULT_EXPORTS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V12 symbol-graph report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
