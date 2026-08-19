"""Recover the exact structural provenance of the stage-one ``prefixUrl``.

V20 proved that webpack export ``12690.S`` owns ``getUploadUrl`` and is
constructed in composition module ``7644`` with a concrete object argument
containing ``prefixUrl``. This probe normalizes only that RHS and nearby alias
assignments.

The normalized expression may contain operators, numeric module IDs, stable
webpack export keys, allowlisted config/method names, hashed local aliases and
public Yandex URL/domain fragments. Ordinary string values, credential values,
raw local identifiers and JavaScript source are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_config_binding_probe as config_probe
import yandex_upload_contract_probe as contract_probe
import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


STAGE1_MODULE_ID = "12690"
COMPOSITION_MODULE_ID = "7644"
TARGET_PROPERTIES = {
    "prefixUrl",
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "authorization",
    "headers",
    "clientRemoteType",
}
ALLOWLISTED_MEMBERS = {
    "getApiPrefixUrl",
    "getClientSafeConfig",
    "getApiToken",
    "getApiTokenValue",
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "apiToken",
    "prefixUrl",
    "clientSafeConfig",
    "clientRemoteType",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "createHttpOptions",
    "authorization",
    "headers",
}
_SAFE_EXPORT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,80}$")
_SAFE_YANDEX_FRAGMENT_RE = re.compile(r"^[A-Za-z0-9_:/.-]{1,200}yandex[A-Za-z0-9_:/.-]{0,200}$", re.IGNORECASE)
_SENSITIVE_RE = re.compile(r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)", re.IGNORECASE)
_ASSIGN_RE = re.compile(r"(?<![A-Za-z0-9_$.])(?P<lhs>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?!=|>)")


def _safe_yandex_literal(value: str) -> str | None:
    clean = value.strip()
    if _SENSITIVE_RE.search(clean):
        return None
    try:
        parsed = urlsplit(clean)
    except ValueError:
        parsed = None
    if parsed and parsed.scheme in {"http", "https"} and parsed.netloc:
        host = (parsed.hostname or "").lower()
        if host == "yandex.ru" or host.endswith(".yandex.ru") or host == "yandex.net" or host.endswith(".yandex.net") or host == "yandex.com" or host.endswith(".yandex.com"):
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))
    if "yandex" in clean.lower() and _SAFE_YANDEX_FRAGMENT_RE.fullmatch(clean):
        return clean
    return None


def _read_js_string(text: str, index: int) -> tuple[str, int]:
    quote = text[index]
    index += 1
    chars: list[str] = []
    escaped = False
    while index < len(text):
        char = text[index]
        if escaped:
            if char in {'"', "'", "`", "\\", "/", ".", ":", "-", "_"}:
                chars.append(char)
            else:
                chars.append("?")
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if char == quote:
            return "".join(chars), index + 1
        if len(chars) < 400:
            chars.append(char)
        index += 1
    return "".join(chars), index


def _member_token(module_id: str, base: str, member: str) -> str:
    if member in ALLOWLISTED_MEMBERS:
        return f"{base}.member:{member}"
    return f"{base}.member:{dataflow_probe._alias(module_id, member)}"  # noqa: SLF001


def _normalized_expression(
    module_id: str,
    expression: str,
    imports: list[dict[str, str]],
    *,
    sensitive_context: bool = False,
) -> list[str]:
    import_map = {item["local"]: item["source_module_id"] for item in imports}
    tokens: list[str] = []
    index = 0
    while index < len(expression) and len(tokens) < 500:
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char in {'"', "'", "`"}:
            literal, index = _read_js_string(expression, index)
            safe = None if sensitive_context else _safe_yandex_literal(literal)
            tokens.append(f"literal:{safe}" if safe else "<string>")
            continue
        if char.isalpha() or char in "_$":
            start = index
            index += 1
            while index < len(expression) and (expression[index].isalnum() or expression[index] in "_$"):
                index += 1
            identifier = expression[start:index]

            # Imported module member: alias.exportKey. Export keys are stable
            # webpack interface identifiers and are safe to preserve.
            if identifier in import_map and index < len(expression) and expression[index] == ".":
                member_start = index + 1
                member_end = member_start
                while member_end < len(expression) and (expression[member_end].isalnum() or expression[member_end] in "_$"):
                    member_end += 1
                member = expression[member_start:member_end]
                if _SAFE_EXPORT_RE.fullmatch(member):
                    tokens.append(f"m{import_map[identifier]}.{member}")
                    index = member_end
                    continue

            # Preserve only explicitly allowlisted config/request members on
            # ``this``. Unknown members are hashed rather than emitted.
            if identifier == "this" and index < len(expression) and expression[index] == ".":
                member_start = index + 1
                member_end = member_start
                while member_end < len(expression) and (expression[member_end].isalnum() or expression[member_end] in "_$"):
                    member_end += 1
                member = expression[member_start:member_end]
                if _SAFE_EXPORT_RE.fullmatch(member):
                    tokens.append(_member_token(module_id, "this", member))
                    index = member_end
                    continue

            if identifier in import_map:
                tokens.append(f"m{import_map[identifier]}")
            elif identifier in TARGET_PROPERTIES:
                tokens.append(f"prop:{identifier}")
            elif identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
                tokens.append(identifier)
            else:
                tokens.append(dataflow_probe._alias(module_id, identifier))  # noqa: SLF001
            continue
        two = expression[index : index + 2]
        three = expression[index : index + 3]
        if three in {"===", "!==", "..."}:
            tokens.append(three)
            index += 3
            continue
        if two in {"||", "&&", "??", "=>", "==", "!=", "?.", "**", ">=", "<="}:
            tokens.append(two)
            index += 2
            continue
        if char in "(){}[]?:+-,.!*/%<>":
            tokens.append(char)
        elif char.isdigit():
            while index + 1 < len(expression) and (expression[index + 1].isdigit() or expression[index + 1] == "."):
                index += 1
            tokens.append("<number>")
        index += 1
    return tokens


def _slice_rhs(text: str, start: int) -> str:
    """Slice one assignment/property RHS up to a top-level separator/closing delimiter."""
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    escaped = False
    index = start
    while index < len(text):
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
        elif char in ")]}":
            if stack and stack[-1] == pairs[char]:
                stack.pop()
            elif not stack:
                break
            else:
                break
        elif not stack and char in ",;":
            break
        index += 1
    return text[start:index].strip()


def _object_property_rhs(object_expression: str, key: str) -> str | None:
    value = object_expression.strip()
    if not (value.startswith("{") and value.endswith("}")):
        return None
    for part in contract_probe._split_top_level(value[1:-1]):  # noqa: SLF001
        colon = config_probe._find_top_level_colon(part)  # noqa: SLF001
        if colon is None:
            continue
        raw_key = part[:colon].strip().strip("\"'")
        if raw_key == key:
            return part[colon + 1 :].strip()
    return None


def _stage1_prefix_expression(composition_body: str) -> tuple[str | None, list[dict[str, str]]]:
    imports = wiring_probe._imports(composition_body)  # noqa: SLF001
    for item in imports:
        if item["source_module_id"] != STAGE1_MODULE_ID:
            continue
        local = item["local"]
        pattern = re.compile(rf"\bnew\s+{re.escape(local)}\.(?P<export>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
        for match in pattern.finditer(composition_body):
            open_paren = composition_body.find("(", match.start(), match.end())
            end = contract_probe._find_matching(composition_body, open_paren, "(", ")")  # noqa: SLF001
            if end is None:
                continue
            args = contract_probe._split_top_level(composition_body[open_paren + 1 : end])  # noqa: SLF001
            for arg in args:
                rhs = _object_property_rhs(arg, "prefixUrl")
                if rhs is not None:
                    return rhs, imports
    return None, imports


def _raw_aliases(expression: str, imports: list[dict[str, str]]) -> list[str]:
    import_locals = {item["local"] for item in imports}
    results: list[str] = []
    for identifier in re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b", expression):
        if identifier in import_locals or identifier in TARGET_PROPERTIES or identifier in dataflow_probe._JS_KEYWORDS:  # noqa: SLF001
            continue
        # Ignore member names following an import/local dot; only roots need provenance.
        if re.search(rf"\.\s*{re.escape(identifier)}\b", expression):
            continue
        if identifier not in results:
            results.append(identifier)
    return results[:80]


def _assignment_map(body: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for match in _ASSIGN_RE.finditer(body):
        lhs = match.group("lhs")
        rhs = _slice_rhs(body, match.end())
        if rhs and lhs not in results:
            results[lhs] = rhs
    return results


def _alias_provenance(
    module_id: str,
    roots: list[str],
    assignments: dict[str, str],
    imports: list[dict[str, str]],
    *,
    max_depth: int = 3,
) -> list[dict[str, Any]]:
    queue: list[tuple[str, int]] = [(root, 0) for root in roots]
    visited: set[str] = set()
    results: list[dict[str, Any]] = []
    while queue:
        raw, depth = queue.pop(0)
        if raw in visited or depth > max_depth:
            continue
        visited.add(raw)
        rhs = assignments.get(raw)
        record: dict[str, Any] = {
            "alias": dataflow_probe._alias(module_id, raw),  # noqa: SLF001
            "definitionFound": rhs is not None,
            "depth": depth,
        }
        if rhs is not None:
            record["normalizedRhs"] = _normalized_expression(module_id, rhs, imports)
            children = _raw_aliases(rhs, imports)
            record["childAliases"] = [dataflow_probe._alias(module_id, child) for child in children]  # noqa: SLF001
            if depth < max_depth:
                queue.extend((child, depth + 1) for child in children)
        results.append(record)
    return results[:160]


def _config_property_bindings(body: str, imports: list[dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for prop in sorted(TARGET_PROPERTIES):
        pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(prop)}\s*:\s*")
        for match in pattern.finditer(body):
            rhs = _slice_rhs(body, match.end())
            if not rhs:
                continue
            item = {
                "property": prop,
                "normalizedRhs": _normalized_expression(
                    COMPOSITION_MODULE_ID,
                    rhs,
                    imports,
                    sensitive_context=prop in {"customApiToken", "authorization"},
                ),
            }
            if item not in results:
                results.append(item)
    return results[:120]


def analyze_composition(body: str) -> dict[str, Any]:
    prefix_rhs, imports = _stage1_prefix_expression(body)
    assignments = _assignment_map(body)
    roots = _raw_aliases(prefix_rhs or "", imports)
    return {
        "module_id": COMPOSITION_MODULE_ID,
        "stage1PrefixFound": prefix_rhs is not None,
        "normalizedStage1Prefix": _normalized_expression(COMPOSITION_MODULE_ID, prefix_rhs or "", imports),
        "prefixRootAliases": [dataflow_probe._alias(COMPOSITION_MODULE_ID, root) for root in roots],  # noqa: SLF001
        "aliasProvenance": _alias_provenance(COMPOSITION_MODULE_ID, roots, assignments, imports),
        "configPropertyBindings": _config_property_bindings(body, imports),
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
        "format": "musicark-yandex-upload-prefix-provenance-v2",
        "source": "asar-stage1-prefix-normalized-provenance",
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
    parser = argparse.ArgumentParser(description="Recover normalized provenance of the official desktop stage-one prefixUrl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one prefix provenance report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
