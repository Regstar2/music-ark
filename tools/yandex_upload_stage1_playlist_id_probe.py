"""Recover the stage-one ``playlistId`` formula without emitting source values.

The probe follows real ``getUploadUrl({...})`` call sites in the official desktop
ASAR and emits a normalized token form for the ``playlistId`` expression plus
nearest assignments for hashed local aliases. Only allowlisted protocol semantic
names, punctuation, webpack module references and deterministic alias hashes are
preserved. Ordinary strings/numbers, JavaScript source, credentials and query
values are never emitted.
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
import yandex_upload_stage1_flow_probe as flow_probe
import yandex_upload_target_probe as target_probe


_SAFE_NAMES = {
    "playlistId",
    "playlistKind",
    "playlistUuid",
    "uid",
    "userId",
    "ownerUid",
    "path",
    "name",
    "fileName",
    "filename",
    "uuid",
    "kind",
    "id",
}
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
_IDENTIFIER_FULL_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_PUNCTUATION = set(".=:+-*/,;(){}[]?!<>|&")


def _normalize_expression(module_id: str, expression: str, imports: list[dict[str, str]]) -> list[str]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    tokens: list[str] = []
    index = 0
    length = len(expression)
    while index < length and len(tokens) < 160:
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char == "/" and index + 1 < length and expression[index + 1] == "/":
            index += 2
            while index < length and expression[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and expression[index + 1] == "*":
            end = expression.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            escaped = False
            while index < length:
                current = expression[index]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    index += 1
                    break
                index += 1
            tokens.append("<string>")
            continue
        if char == "`":
            index += 1
            tokens.append("<template>")
            escaped = False
            while index < length:
                current = expression[index]
                if escaped:
                    escaped = False
                    index += 1
                    continue
                if current == "\\":
                    escaped = True
                    index += 1
                    continue
                if current == "`":
                    index += 1
                    break
                if current == "$" and index + 1 < length and expression[index + 1] == "{":
                    open_brace = index + 1
                    close = contract_probe._find_matching(expression, open_brace, "{", "}")  # noqa: SLF001
                    if close is None:
                        index = length
                        break
                    tokens.extend(["${", *_normalize_expression(module_id, expression[open_brace + 1 : close], imports), "}"])
                    index = close + 1
                    continue
                index += 1
            continue
        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < length and (expression[index].isalnum() or expression[index] in "_$"):
                index += 1
            identifier = expression[start:index]
            if identifier in _SAFE_NAMES:
                tokens.append(identifier)
            elif identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
                tokens.append(identifier)
            elif identifier in import_map:
                tokens.append(f"module:{import_map[identifier]}")
            else:
                tokens.append(dataflow_probe._alias(module_id, identifier))  # noqa: SLF001
            continue
        if char.isdigit():
            index += 1
            while index < length and (expression[index].isdigit() or expression[index] == "."):
                index += 1
            tokens.append("<number>")
            continue
        if char in _PUNCTUATION:
            tokens.append(char)
        index += 1
    return tokens[:160]


def _safe_object_values(expression: str) -> dict[str, str]:
    value = expression.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return {}
    result: dict[str, str] = {}
    for part in contract_probe._split_top_level(value[1:-1]):  # noqa: SLF001
        fragment = part.strip()
        if not fragment or fragment.startswith("..."):
            continue
        colon = config_probe._find_top_level_colon(fragment)  # noqa: SLF001
        if colon is None:
            key = fragment.strip()
            if key in _SAFE_NAMES:
                result[key] = fragment
            continue
        key = fragment[:colon].strip().strip("\"'")
        if key in _SAFE_NAMES:
            result[key] = fragment[colon + 1 :].strip()
    return result


def _local_identifiers(expression: str, imports: list[dict[str, str]]) -> list[str]:
    import_locals = {item["local"] for item in imports}
    result: list[str] = []
    for identifier in _IDENTIFIER_RE.findall(expression):
        if identifier in _SAFE_NAMES or identifier in import_locals or identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
            continue
        if identifier not in result:
            result.append(identifier)
    return result[:24]


def _alias_assignments(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    *,
    body: str,
    before: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for identifier in _local_identifiers(expression, imports):
        assigned = flow_probe._nearest_assignment(body, identifier, before)  # noqa: SLF001
        if not assigned:
            continue
        results.append(
            {
                "alias": dataflow_probe._alias(module_id, identifier),  # noqa: SLF001
                "normalizedAssignment": _normalize_expression(module_id, assigned, imports),
                "semanticNames": flow_probe._semantic_names(assigned),  # noqa: SLF001
                "sourceRefs": flow_probe._source_refs(assigned, imports),  # noqa: SLF001
            }
        )
    return results[:24]


def _call_records(module_id: str, body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    pattern = re.compile(r"(?:\?\.|\.)getUploadUrl\s*\(")
    for match in pattern.finditer(body):
        open_paren = body.find("(", match.start(), match.end())
        close = contract_probe._find_matching(body, open_paren, "(", ")")  # noqa: SLF001
        if close is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1 : close])  # noqa: SLF001
        if not args:
            continue
        values = _safe_object_values(args[0])
        playlist_id = values.get("playlistId")
        if not playlist_id:
            continue
        uid_expr = values.get("uid", "")
        path_expr = values.get("path", "")
        playlist_kind_expr = values.get("playlistKind", "")
        playlist_aliases = set(flow_probe._alias_refs(module_id, playlist_id, imports))  # noqa: SLF001
        uid_aliases = set(flow_probe._alias_refs(module_id, uid_expr, imports)) if uid_expr else set()  # noqa: SLF001
        path_aliases = set(flow_probe._alias_refs(module_id, path_expr, imports)) if path_expr else set()  # noqa: SLF001
        results.append(
            {
                "playlistId": {
                    "normalizedExpression": _normalize_expression(module_id, playlist_id, imports),
                    "semanticNames": flow_probe._semantic_names(playlist_id),  # noqa: SLF001
                    "sourceRefs": flow_probe._source_refs(playlist_id, imports),  # noqa: SLF001
                    "aliasAssignments": _alias_assignments(
                        module_id,
                        playlist_id,
                        imports,
                        body=body,
                        before=match.start(),
                    ),
                },
                "playlistKind": {
                    "present": bool(playlist_kind_expr),
                    "normalizedExpression": _normalize_expression(module_id, playlist_kind_expr, imports) if playlist_kind_expr else [],
                },
                "uid": {
                    "present": bool(uid_expr),
                    "normalizedExpression": _normalize_expression(module_id, uid_expr, imports) if uid_expr else [],
                },
                "path": {
                    "present": bool(path_expr),
                    "normalizedExpression": _normalize_expression(module_id, path_expr, imports) if path_expr else [],
                },
                "relationships": {
                    "playlistIdSharesAliasWithUid": bool(playlist_aliases & uid_aliases),
                    "playlistIdSharesAliasWithPath": bool(playlist_aliases & path_aliases),
                },
            }
        )
    return results[:40]


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
            calls = _call_records(module["module_id"], module["body"])
            if calls:
                modules.append(
                    {
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        "module_id": module["module_id"],
                        "calls": calls,
                    }
                )
    return {
        "format": "musicark-yandex-upload-stage1-playlist-id-v1",
        "source": "asar-stage1-playlist-id-normalized-dataflow",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "modules": modules[:80],
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
    parser = argparse.ArgumentParser(description="Recover the secret-free stage-one playlistId formula.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one playlist-id report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
