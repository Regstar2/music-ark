"""Recover only safe literal/method details of the stage-one playlist-id formula.

This offline ASAR probe complements V46. It exposes only allowlisted standard
string method names and empty/punctuation-only string literals from the real
``playlistId`` expression. All ordinary strings, local identifiers, credentials,
request values and JavaScript source remain redacted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_stage1_playlist_id_probe as playlist_probe
import yandex_upload_target_probe as target_probe


_SAFE_IDENTIFIERS = {"uid", "playlistKind", "concat"}
_SAFE_STRING_METHODS = {"concat"}
_SAFE_PUNCTUATION_CHARS = set("-_:/.|~")
_PUNCTUATION = set(".=:+-*/,;(){}[]?!<>|&")


def _decode_simple_js_string(raw: str) -> str | None:
    """Decode only a tiny safe subset needed for punctuation-only literals."""
    if len(raw) < 2 or raw[0] not in {'\"', "'"} or raw[-1] != raw[0]:
        return None
    body = raw[1:-1]
    result: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue
        index += 1
        if index >= len(body):
            return None
        escaped = body[index]
        if escaped in {"\\", "'", '"'}:
            result.append(escaped)
            index += 1
            continue
        return None
    return "".join(result)


def _safe_string_token(raw: str) -> dict[str, Any]:
    value = _decode_simple_js_string(raw)
    if value is None:
        return {"kind": "redacted-string"}
    if value == "":
        return {"kind": "empty-string"}
    if len(value) <= 8 and all(char in _SAFE_PUNCTUATION_CHARS for char in value):
        return {"kind": "punctuation-string", "value": value}
    return {"kind": "redacted-string"}


def _tokenize_formula(module_id: str, expression: str, imports: list[dict[str, str]]) -> list[Any]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    tokens: list[Any] = []
    index = 0
    while index < len(expression) and len(tokens) < 160:
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char in {'\"', "'"}:
            quote = char
            start = index
            index += 1
            escaped = False
            while index < len(expression):
                current = expression[index]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    index += 1
                    break
                index += 1
            tokens.append(_safe_string_token(expression[start:index]))
            continue
        if char == "`":
            # Template text may contain ordinary strings; V46 already reports
            # interpolation structure, so V47 keeps templates fully redacted.
            tokens.append({"kind": "redacted-template"})
            index += 1
            escaped = False
            while index < len(expression):
                current = expression[index]
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == "`":
                    index += 1
                    break
                index += 1
            continue
        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < len(expression) and (expression[index].isalnum() or expression[index] in "_$"):
                index += 1
            identifier = expression[start:index]
            if identifier in _SAFE_IDENTIFIERS:
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
            while index < len(expression) and (expression[index].isdigit() or expression[index] == "."):
                index += 1
            tokens.append("<number>")
            continue
        if char in _PUNCTUATION:
            tokens.append(char)
        index += 1
    return tokens[:160]


def _formula_records(module_id: str, body: str) -> list[dict[str, Any]]:
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
        values = playlist_probe._safe_object_values(args[0])  # noqa: SLF001
        expression = values.get("playlistId")
        if not expression:
            continue
        tokens = _tokenize_formula(module_id, expression, imports)
        methods = sorted({token for token in tokens if isinstance(token, str) and token in _SAFE_STRING_METHODS})
        safe_literals = [token for token in tokens if isinstance(token, dict)]
        results.append(
            {
                "formulaTokens": tokens,
                "safeStringMethods": methods,
                "safeStringLiterals": safe_literals,
                "containsUid": "uid" in tokens,
                "containsPlaylistKind": "playlistKind" in tokens,
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
            records = _formula_records(module["module_id"], module["body"])
            if records:
                modules.append(
                    {
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        "module_id": module["module_id"],
                        "records": records,
                    }
                )
    return {
        "format": "musicark-yandex-upload-stage1-playlist-id-literal-v1",
        "source": "asar-stage1-playlist-id-safe-literal-dataflow",
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
    parser = argparse.ArgumentParser(description="Recover safe literal details of the stage-one playlistId formula.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one playlist-id literal report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
