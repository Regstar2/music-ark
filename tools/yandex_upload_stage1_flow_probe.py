"""Trace stage-one upload call-site semantics without emitting source values.

This offline ASAR probe focuses on callers of ``getUploadUrl`` and the later
upload-center lifecycle methods. It preserves only allowlisted protocol semantic
names, webpack module IDs/export keys, structural expression kinds and hashed
local aliases. JavaScript source, ordinary strings, credentials, header/query
values and raw local identifiers are never emitted.
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


_METHODS = (
    "getUploadUrl",
    "moveTracksFromUploadCenterToPlaylist",
    "checkProcessingTracks",
)
_SEMANTIC_NAMES = {
    "getUploadUrl",
    "moveTracksFromUploadCenterToPlaylist",
    "checkProcessingTracks",
    "playlistId",
    "playlistKind",
    "playlistUuid",
    "playlistUUID",
    "targetPlaylistId",
    "targetPlaylistKind",
    "uploadCenter",
    "uploadCenterId",
    "uploadCenterPlaylistId",
    "uploadPlaylistId",
    "uid",
    "userId",
    "ownerUid",
    "path",
    "fileName",
    "filename",
    "name",
    "visibility",
    "uuid",
    "kind",
    "id",
    "trackId",
    "trackIds",
    "ugcTrackId",
}
_SAFE_KEY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$-]{0,100}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_IDENTIFIER_FIND_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
_MEMBER_FIND_RE = re.compile(r"\.([A-Za-z_$][A-Za-z0-9_$]*)")


def _hash_key(value: str) -> str:
    return "key:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _safe_key(value: str) -> str:
    clean = value.strip().strip("\"'")
    if not _SAFE_KEY_RE.fullmatch(clean):
        return "key:invalid"
    return clean if clean in _SEMANTIC_NAMES else _hash_key(clean)


def _kind(expression: str) -> str:
    value = expression.strip()
    if not value:
        return "empty"
    if _IDENTIFIER_RE.fullmatch(value):
        return "identifier"
    if value.startswith("{"):
        return "object"
    if value.startswith("["):
        return "array"
    if re.match(r"^(?:new\s+)?[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*\s*\(", value):
        return "call"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+", value):
        return "member"
    if value in {"true", "false"}:
        return "boolean"
    if value == "null":
        return "null"
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return "number"
    if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
        return "string"
    return "expression"


def _semantic_names(expression: str) -> list[str]:
    found: list[str] = []
    for name in _IDENTIFIER_FIND_RE.findall(expression):
        if name in _SEMANTIC_NAMES and name not in found:
            found.append(name)
    for name in _MEMBER_FIND_RE.findall(expression):
        if name in _SEMANTIC_NAMES and name not in found:
            found.append(name)
    return sorted(found)


def _source_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        local = item["local"]
        source_id = item["source_module_id"]
        matched = False
        pattern = re.compile(rf"\b{re.escape(local)}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]*)")
        for match in pattern.finditer(expression):
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
    for identifier in _IDENTIFIER_FIND_RE.findall(expression):
        if identifier in _SEMANTIC_NAMES or identifier in import_locals or identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
            continue
        alias = dataflow_probe._alias(module_id, identifier)  # noqa: SLF001
        if alias not in results:
            results.append(alias)
    return results[:40]


def _slice_rhs(text: str, start: int, *, limit: int) -> str:
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    escaped = False
    index = start
    end = min(len(text), limit)
    while index < end:
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'", "`"}:
            quote = char
            index += 1
            continue
        if char in "([{":
            stack.append(char)
            index += 1
            continue
        if char in ")]}" and stack and stack[-1] == pairs[char]:
            stack.pop()
            index += 1
            continue
        if not stack and char in {",", ";"}:
            break
        index += 1
    return text[start:index].strip()


def _nearest_assignment(text: str, identifier: str, before: int) -> str | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(identifier)}\s*=\s*")
    matches = [match for match in pattern.finditer(text, 0, before)]
    for match in reversed(matches[-20:]):
        rhs = _slice_rhs(text, match.end(), limit=before)
        if rhs:
            return rhs
    return None


def _summary(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    *,
    body: str,
    before: int,
) -> dict[str, Any]:
    value = expression.strip()
    result: dict[str, Any] = {
        "kind": _kind(value),
        "semanticNames": _semantic_names(value),
        "sourceRefs": _source_refs(value, imports),
        "aliasRefs": _alias_refs(module_id, value, imports),
    }
    if _IDENTIFIER_RE.fullmatch(value) and value not in _SEMANTIC_NAMES:
        assigned = _nearest_assignment(body, value, before)
        if assigned:
            result["nearestAssignment"] = {
                "kind": _kind(assigned),
                "semanticNames": _semantic_names(assigned),
                "sourceRefs": _source_refs(assigned, imports),
                "aliasRefs": _alias_refs(module_id, assigned, imports),
            }
    return result


def _object_map(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    *,
    body: str,
    before: int,
) -> list[dict[str, Any]]:
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
            if _IDENTIFIER_RE.fullmatch(fragment):
                results.append(
                    {
                        "key": _safe_key(fragment),
                        "relation": "shorthand",
                        "value": _summary(module_id, fragment, imports, body=body, before=before),
                    }
                )
            continue
        raw_key = fragment[:colon].strip()
        rhs = fragment[colon + 1 :].strip()
        results.append(
            {
                "key": _safe_key(raw_key),
                "relation": "property",
                "value": _summary(module_id, rhs, imports, body=body, before=before),
            }
        )
    return results[:120]


def _calls(module_id: str, body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    for method in _METHODS:
        pattern = re.compile(rf"(?:\?\.|\.){re.escape(method)}\s*\(")
        for match in pattern.finditer(body):
            open_paren = body.find("(", match.start(), match.end())
            close = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
            if close is None:
                continue
            args = contract_probe._split_top_level(body[open_paren + 1 : close])  # noqa: SLF001
            arguments: list[dict[str, Any]] = []
            for index, arg in enumerate(args[:12]):
                item: dict[str, Any] = {
                    "index": index,
                    "value": _summary(module_id, arg, imports, body=body, before=match.start()),
                }
                object_properties = _object_map(
                    module_id,
                    arg,
                    imports,
                    body=body,
                    before=match.start(),
                )
                if object_properties:
                    item["objectProperties"] = object_properties
                arguments.append(item)
            results.append(
                {
                    "method": method,
                    "argumentCount": len(args),
                    "arguments": arguments,
                }
            )
    return results[:160]


def analyze_module(module_id: str, body: str) -> dict[str, Any] | None:
    calls = _calls(module_id, body)
    anchors = [name for name in _METHODS if name in body]
    semantic_names = sorted({name for name in _SEMANTIC_NAMES if re.search(rf"\b{re.escape(name)}\b", body)})
    if not calls:
        return None
    encoded_calls = json.dumps(calls, ensure_ascii=False)
    upload_center_evidence = any(
        name in encoded_calls
        for name in ("uploadCenter", "uploadCenterId", "uploadCenterPlaylistId", "uploadPlaylistId")
    )
    return {
        "module_id": module_id,
        "anchorsPresent": anchors,
        "semanticNamesPresent": semantic_names,
        "uploadCenterEvidence": upload_center_evidence,
        "calls": calls,
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
    modules: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            analysis = analyze_module(module["module_id"], module["body"])
            if analysis is not None:
                modules.append(
                    {
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        **analysis,
                    }
                )
    return {
        "format": "musicark-yandex-upload-stage1-flow-v1",
        "source": "asar-stage1-callsite-semantic-dataflow",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "modules": modules[:240],
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
    parser = argparse.ArgumentParser(description="Trace secret-free stage-one playlist/upload-center call-site semantics.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one flow report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
