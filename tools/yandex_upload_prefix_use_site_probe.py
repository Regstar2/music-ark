"""Trace getTldHost arguments using nearest use-site assignments.

Minified webpack modules may reuse a local identifier after its initial require
binding. This probe starts at the proven getTldHost call and walks the nearest
preceding assignment for each simple local argument. It emits only hashed alias
IDs, normalized structural RHS tokens and allowlisted public Yandex templates.
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
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
HELPER_MODULE_ID = "91953"
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")
_SAFE_TEMPLATE_RE = re.compile(r"^https?://[A-Za-z0-9._:{}$%+\-]*yandex[A-Za-z0-9._:{}$%+\-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+\-]*)?$", re.IGNORECASE)
_SENSITIVE_RE = re.compile(r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)", re.IGNORECASE)


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _safe_template(value: str) -> str | None:
    clean = value.strip()
    if not clean or "?" in clean or "#" in clean or _SENSITIVE_RE.search(clean):
        return None
    return clean if _SAFE_TEMPLATE_RE.fullmatch(clean) else None


def _safe_literals(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        safe = _safe_template(value)
        if safe and safe not in results:
            results.append(safe)
    return results[:20]


def _call(body: str) -> tuple[int, list[str]] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    for item in imports:
        if item["source_module_id"] != HELPER_MODULE_ID:
            continue
        marker = re.search(rf"{re.escape(item['local'])}\.getTldHost", body)
        if not marker:
            continue
        open_paren = body.find("(", marker.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1:end])  # noqa: SLF001
        if len(args) == 3:
            return marker.start(), [arg.strip() for arg in args]
    return None


def _nearest_assignment(body: str, identifier: str, before: int) -> tuple[int, str] | None:
    if not _SAFE_IDENTIFIER_RE.fullmatch(identifier):
        return None
    pattern = re.compile(rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)")
    matches = [match for match in pattern.finditer(body, 0, before)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if rhs:
            return match.start(), rhs.strip()
    return None


def _trace_argument(body: str, expression: str, call_pos: int, imports: list[dict[str, str]], *, max_depth: int = 6) -> dict[str, Any]:
    current = expression.strip()
    before = call_pos
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    for depth in range(max_depth + 1):
        normalized = prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, current, imports)  # noqa: SLF001
        record: dict[str, Any] = {
            "depth": depth,
            "expressionKind": "identifier" if _SAFE_IDENTIFIER_RE.fullmatch(current) else "expression",
            "normalized": normalized,
            "safeYandexTemplates": _safe_literals(current),
        }
        if _SAFE_IDENTIFIER_RE.fullmatch(current):
            record["aliasHash"] = dataflow_probe._alias(COMPOSITION_MODULE_ID, current)  # noqa: SLF001
        chain.append(record)
        if not _SAFE_IDENTIFIER_RE.fullmatch(current) or current in seen:
            break
        seen.add(current)
        assigned = _nearest_assignment(body, current, before)
        if not assigned:
            break
        position, rhs = assigned
        record["nearestAssignmentFound"] = True
        current = rhs
        before = position
    return {"chain": chain}


def analyze_body(body: str) -> dict[str, Any]:
    found = _call(body)
    if not found:
        return {"callFound": False}
    call_pos, args = found
    imports = wiring_probe._imports(body)  # noqa: SLF001
    return {
        "callFound": True,
        "arguments": [
            {"index": index, **_trace_argument(body, arg, call_pos, imports)}
            for index, arg in enumerate(args)
        ],
    }


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
            if module["module_id"] == COMPOSITION_MODULE_ID:
                matches.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": COMPOSITION_MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-prefix-use-site-v1",
        "source": "asar-stage1-prefix-use-site-assignment-trace",
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
    parser = argparse.ArgumentParser(description="Trace getTldHost arguments at their exact use site safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized prefix use-site report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
