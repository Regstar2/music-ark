"""Resolve the local/closure value consumed by the stage-one OAuth header.

The request class ``31322.X`` is already proven to emit ``OAuth <value>`` while
not referencing ``customApiToken``. This probe identifies the bare local used in
that authorization expression and traces its nearest assignment/destructuring
source within the class/module. Local names are hashed. Exact non-sensitive
semantic properties such as ``oauth`` or ``config`` may be emitted; values never
are.
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
import yandex_upload_oauth_origin_probe as origin_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_request_stack_probe as stack_probe
import yandex_upload_runtime_dataflow_probe as dataflow_probe
import yandex_upload_target_probe as target_probe


MODULE_ID = "31322"
EXPORT_KEY = "X"
_SEMANTIC_PROPERTIES = {"oauth", "authorization", "config", "httpClient", "headers", "prefixUrl", "clientRemoteType", "account", "user"}
_SENSITIVE_PROPERTY_RE = re.compile(r"(?:secret|cookie|session|password|credential|signature|customApiToken)", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")


def _hash(value: str) -> str:
    return dataflow_probe._alias(MODULE_ID, value)  # noqa: SLF001


def _safe_property(value: str) -> str:
    if value in _SEMANTIC_PROPERTIES:
        return value
    return "property:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _authorization_candidate(class_fragment: str) -> tuple[str, int] | None:
    patterns = (
        re.compile(r"(?<![A-Za-z0-9_$])authorization\s*:\s*"),
        re.compile(r"[\"']authorization[\"']\s*:\s*"),
    )
    for pattern in patterns:
        match = pattern.search(class_fragment)
        if not match:
            continue
        rhs = prefix_probe._slice_rhs(class_fragment, match.end())  # noqa: SLF001
        if not rhs:
            continue
        constructor = origin_probe._constructor_details(class_fragment)  # noqa: SLF001
        details = origin_probe._rhs_origins(rhs, constructor)  # noqa: SLF001
        bare = details.get("bareAliases") or []
        if not bare:
            continue
        target_hash = bare[0]["aliasHash"]
        for identifier in _IDENTIFIER_RE.findall(rhs):
            if _hash(identifier) == target_hash:
                return identifier, match.start()
    return None


def _safe_member_path(expression: str) -> list[str] | None:
    clean = re.sub(r"\s+", "", expression)
    match = re.fullmatch(r"this\.([A-Za-z_$][A-Za-z0-9_$]*)(?:\.([A-Za-z_$][A-Za-z0-9_$]*))?", clean)
    if not match:
        return None
    values = [item for item in match.groups() if item]
    if any(_SENSITIVE_PROPERTY_RE.search(item) for item in values):
        return None
    return ["this", *[_safe_property(item) for item in values]]


def _constructor_param_source(class_fragment: str, identifier: str) -> dict[str, Any] | None:
    match = re.search(r"\bconstructor\s*\((?P<params>[^()]*)\)\s*\{", class_fragment)
    if not match:
        return None
    params = [item.strip() for item in contract_probe._split_top_level(match.group("params")) if item.strip()]  # noqa: SLF001
    if identifier in params:
        return {"kind": "constructor-param", "index": params.index(identifier)}
    return None


def _nearest_simple_assignment(class_fragment: str, identifier: str, before: int) -> dict[str, Any] | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)")
    matches = [match for match in pattern.finditer(class_fragment, 0, before)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(class_fragment, match.end())  # noqa: SLF001
        if not rhs:
            continue
        member_path = _safe_member_path(rhs)
        if member_path:
            return {"kind": "this-member", "path": member_path}
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", rhs.strip()):
            return {"kind": "local-alias", "aliasHash": _hash(rhs.strip())}
        return {"kind": "expression", "normalized": prefix_probe._normalized_expression(MODULE_ID, rhs, [])}  # noqa: SLF001
    return None


def _destructure_source(class_fragment: str, identifier: str, before: int) -> dict[str, Any] | None:
    # Match only the semantic `oauth` property; arbitrary destructured keys are
    # irrelevant to the proven OAuth header and are not emitted.
    patterns = (
        re.compile(rf"\{{[^{{}}]*\boauth\s*:\s*{re.escape(identifier)}\b[^{{}}]*\}}\s*=\s*"),
        re.compile(rf"\{{[^{{}}]*\b{re.escape(identifier)}\b[^{{}}]*\}}\s*=\s*"),
    )
    for pattern in patterns:
        matches = [match for match in pattern.finditer(class_fragment, 0, before)]
        for match in reversed(matches):
            rhs = prefix_probe._slice_rhs(class_fragment, match.end())  # noqa: SLF001
            if not rhs:
                continue
            member_path = _safe_member_path(rhs)
            return {
                "kind": "object-destructure",
                "property": "oauth",
                "sourcePath": member_path,
                "sourceNormalized": None if member_path else prefix_probe._normalized_expression(MODULE_ID, rhs, []),  # noqa: SLF001
            }
    return None


def _module_assignment_source(body: str, identifier: str, class_start: int) -> dict[str, Any] | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_$])(?:var\s+|let\s+|const\s+)?{re.escape(identifier)}\s*=\s*(?!=|>)")
    matches = [match for match in pattern.finditer(body, 0, class_start)]
    for match in reversed(matches):
        rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
        if not rhs:
            continue
        imports = wiring_probe._imports(body)  # noqa: SLF001
        refs: list[dict[str, str]] = []
        for item in imports:
            member = re.fullmatch(rf"{re.escape(item['local'])}\.(?P<key>[A-Za-z_$][A-Za-z0-9_$]*)", rhs.strip())
            if member:
                refs.append({"source_module_id": item["source_module_id"], "export_key": member.group("key")})
        return {
            "kind": "module-assignment",
            "importRefs": refs,
            "normalized": prefix_probe._normalized_expression(MODULE_ID, rhs, imports),  # noqa: SLF001
        }
    return None


def analyze_body(body: str) -> dict[str, Any]:
    found = stack_probe._class_span(body, EXPORT_KEY)  # noqa: SLF001
    if not found:
        return {"classResolved": False}
    _, span, class_fragment = found
    candidate = _authorization_candidate(class_fragment)
    if not candidate:
        return {"classResolved": True, "authorizationLocalResolved": False}
    identifier, before = candidate
    source = (
        _destructure_source(class_fragment, identifier, before)
        or _nearest_simple_assignment(class_fragment, identifier, before)
        or _constructor_param_source(class_fragment, identifier)
        or _module_assignment_source(body, identifier, int(span["start"]))
        or {"kind": "unresolved-closure"}
    )
    return {
        "classResolved": True,
        "authorizationLocalResolved": True,
        "authorizationLocalHash": _hash(identifier),
        "source": source,
        "customApiTokenReferenced": "customApiToken" in class_fragment,
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    analyses: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            if module["module_id"] == MODULE_ID:
                analyses.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-oauth-binding-v1",
        "source": "asar-stage1-oauth-local-binding-lineage",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "analyses": analyses[:20],
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
    parser = argparse.ArgumentParser(description="Trace the local value feeding the stage-one OAuth header safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized OAuth-binding report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
