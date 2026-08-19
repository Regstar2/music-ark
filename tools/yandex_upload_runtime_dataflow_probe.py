"""Trace upload runtime config dataflow with hashed local identifiers.

The probe tokenizes JavaScript modules without emitting source or string values.
Only allowlisted upload/config property names are preserved. All other local
identifiers are replaced with deterministic short hashes scoped to the webpack
module, allowing structural paths such as
``customApiToken -> alias:<hash> -> authorization`` to be reported without
exposing minified identifiers or credential values.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


TARGETS = {
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "prefixUrl",
    "authorization",
    "headers",
    "clientRemoteType",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "getApiPrefixUrl",
    "getClientSafeConfig",
    "clientSafeConfig",
    "getUploadUrl",
}
SOURCE_TARGET_PAIRS = (
    ("customApiToken", "authorization"),
    ("customApiPrefixUrl", "prefixUrl"),
    ("apiPrefixUrl", "prefixUrl"),
    ("clientRemoteType", "createRequestHeaders"),
    ("clientSafeConfig", "createHttpOptions"),
)
_TEXT_SUFFIXES = {".js"}
_PUNCTUATION = set(".=:+-*/,;(){}[]?!<>")
_JS_KEYWORDS = {
    "as",
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "false",
    "finally",
    "for",
    "from",
    "function",
    "get",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "null",
    "of",
    "return",
    "set",
    "static",
    "super",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "typeof",
    "undefined",
    "var",
    "void",
    "while",
    "with",
    "yield",
}


def _is_identifier_start(char: str) -> bool:
    return char.isalpha() or char in "_$"


def _is_identifier_part(char: str) -> bool:
    return char.isalnum() or char in "_$"


def tokenize(text: str) -> list[str]:
    """Return identifiers/punctuation while replacing ordinary strings entirely."""
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            index += 2
            while index < length and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            index = length if end < 0 else end + 2
            continue
        if char in {'"', "'", "`"}:
            quote = char
            index += 1
            value_chars: list[str] = []
            escaped = False
            interpolation = False
            while index < length:
                current = text[index]
                if escaped:
                    escaped = False
                    value_chars.append("?")
                    index += 1
                    continue
                if current == "\\":
                    escaped = True
                    index += 1
                    continue
                if quote == "`" and current == "$" and index + 1 < length and text[index + 1] == "{":
                    interpolation = True
                if current == quote:
                    index += 1
                    break
                if len(value_chars) <= 160:
                    value_chars.append(current)
                index += 1
            value = "".join(value_chars)
            if not interpolation and value in TARGETS:
                tokens.append(value)
            else:
                tokens.append("<string>")
            continue
        if _is_identifier_start(char):
            start = index
            index += 1
            while index < length and _is_identifier_part(text[index]):
                index += 1
            tokens.append(text[start:index])
            continue
        if char in _PUNCTUATION:
            tokens.append(char)
        index += 1
    return tokens


def _alias(module_id: str, identifier: str) -> str:
    digest = hashlib.sha256(f"{module_id}:{identifier}".encode("utf-8")).hexdigest()[:12]
    return f"alias:{digest}"


def _node(module_id: str, token: str) -> str | None:
    if token in TARGETS:
        return token
    if token in _JS_KEYWORDS:
        return None
    if token == "<string>" or not token or not _is_identifier_start(token[0]):
        return None
    if all(_is_identifier_part(char) for char in token):
        return _alias(module_id, token)
    return None


def build_local_graph(module_id: str, tokens: list[str], *, radius: int = 16) -> dict[str, set[str]]:
    """Connect target properties to nearby hashed aliases inside one expression window."""
    graph: dict[str, set[str]] = defaultdict(set)
    for index, token in enumerate(tokens):
        if token not in TARGETS:
            continue
        left = index
        steps = 0
        while left > 0 and steps < radius and tokens[left - 1] not in {";", "{", "}"}:
            left -= 1
            steps += 1
        right = index
        steps = 0
        while right + 1 < len(tokens) and steps < radius and tokens[right + 1] not in {";", "{", "}"}:
            right += 1
            steps += 1
        center = token
        for nearby in tokens[left : right + 1]:
            node = _node(module_id, nearby)
            if node is None or node == center:
                continue
            graph[center].add(node)
            graph[node].add(center)
    return graph


def _shortest_path(graph: dict[str, set[str]], start: str, target: str, *, max_edges: int = 5) -> list[str] | None:
    if start == target:
        return [start]
    queue: deque[list[str]] = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_edges:
            continue
        for child in sorted(graph.get(path[-1], set())):
            if child == target:
                return [*path, child]
            if child not in visited:
                visited.add(child)
                queue.append([*path, child])
    return None


def module_report(module_id: str, body: str) -> dict[str, Any] | None:
    tokens = tokenize(body)
    targets = sorted({token for token in tokens if token in TARGETS})
    if not targets:
        return None
    graph = build_local_graph(module_id, tokens)
    paths: list[dict[str, Any]] = []
    for source, sink in SOURCE_TARGET_PAIRS:
        if source not in targets or sink not in targets:
            continue
        path = _shortest_path(graph, source, sink)
        if path:
            paths.append({"source": source, "sink": sink, "path": path})
    return {
        "module_id": module_id,
        "targets": targets,
        "paths": paths,
        "hashed_alias_count": len({node for node in graph if node.startswith("alias:")}),
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
    members: list[dict[str, Any]] = []
    aggregate_paths: list[dict[str, Any]] = []

    for entry in entries:
        if Path(entry["path"]).suffix.lower() not in _TEXT_SUFFIXES or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        if not any(target in text for target in TARGETS):
            continue
        module_records: list[dict[str, Any]] = []
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            record = module_report(module["module_id"], module["body"])
            if record is None:
                continue
            module_records.append(record)
            for path_record in record["paths"]:
                aggregate_paths.append(
                    {
                        "member_path": entry["path"],
                        "module_id": record["module_id"],
                        **path_record,
                    }
                )
        if module_records:
            members.append(
                {
                    "path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "modules": module_records[:300],
                }
            )

    return {
        "format": "musicark-yandex-upload-runtime-dataflow-v1",
        "source": "asar-tokenized-hashed-def-use-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "target_pairs": [{"source": source, "sink": sink} for source, sink in SOURCE_TARGET_PAIRS],
        "aggregate_paths": aggregate_paths[:500],
        "members": members[:300],
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "ordinary_string_values_included": False,
            "raw_identifiers_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trace upload config origins using tokenized hashed local identifiers.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime dataflow report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
