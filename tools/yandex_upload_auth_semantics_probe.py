"""Resolve authorization/oauth expression semantics for request module 31322.X.

The probe inspects only the proven request class in the stage-one inheritance
chain. It emits allowlisted property references, stable imported module/export
references, public authorization scheme labels, and normalized structural RHS
tokens. Credential/header values and arbitrary strings are never emitted.
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
import yandex_upload_request_stack_probe as stack_probe
import yandex_upload_target_probe as target_probe


REQUEST_MODULE_ID = "31322"
REQUEST_EXPORT_KEY = "X"
ALLOWLIST = (
    "authorization",
    "oauth",
    "headers",
    "prefixUrl",
    "httpClient",
    "createHttpOptions",
    "createRequestHeaders",
    "clientRemoteType",
    "session",
    "token",
)
_PUBLIC_SCHEMES = {"OAuth", "OAuth ", "Bearer", "Bearer "}
_BINDING_KEYS = ("authorization", "oauth")


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _public_schemes(expression: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(expression):
        if expression[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(expression, index)  # noqa: SLF001
        if value in _PUBLIC_SCHEMES and value not in results:
            results.append(value.strip())
    return results


def _allowlisted_refs(expression: str) -> list[str]:
    results: list[str] = []
    for name in ALLOWLIST:
        if re.search(rf"\b{re.escape(name)}\b", expression):
            results.append(name)
    return results


def _import_refs(body: str, expression: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in wiring_probe._imports(body):  # noqa: SLF001
        pattern = re.compile(rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})")
        for match in pattern.finditer(expression):
            record = {"source_module_id": item["source_module_id"], "export_key": match.group("member")}
            if record not in results:
                results.append(record)
    return results[:40]


def _binding_records(body: str, class_fragment: str, key: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    patterns = (
        ("object-property", re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(key)}\s*:\s*")),
        ("member-assignment", re.compile(rf"\.{re.escape(key)}\s*=\s*(?!=)")),
        ("quoted-property", re.compile(rf"[\"']{re.escape(key)}[\"']\s*:\s*")),
    )
    results: list[dict[str, Any]] = []
    for relation, pattern in patterns:
        for match in pattern.finditer(class_fragment):
            rhs = prefix_probe._slice_rhs(class_fragment, match.end())  # noqa: SLF001
            if not rhs:
                continue
            record = {
                "key": key,
                "relation": relation,
                "allowlistedRefs": _allowlisted_refs(rhs),
                "importMemberRefs": _import_refs(body, rhs),
                "publicSchemes": _public_schemes(rhs),
                "normalizedRhs": prefix_probe._normalized_expression(REQUEST_MODULE_ID, rhs, imports),  # noqa: SLF001
            }
            if record not in results:
                results.append(record)
    return results[:40]


def _method_details(body: str, class_fragment: str) -> list[dict[str, Any]]:
    results = []
    for name in ("createHttpOptions", "createRequestHeaders"):
        summary = stack_probe._method_summary(REQUEST_MODULE_ID, body, class_fragment, name)  # noqa: SLF001
        if summary is not None:
            results.append(summary)
    return results


def analyze_body(body: str) -> dict[str, Any]:
    found = stack_probe._class_span(body, REQUEST_EXPORT_KEY)  # noqa: SLF001
    if not found:
        return {"classResolved": False}
    _, _, class_fragment = found
    bindings = []
    for key in _BINDING_KEYS:
        bindings.extend(_binding_records(body, class_fragment, key))
    return {
        "classResolved": True,
        "allowlistedNames": [name for name in ALLOWLIST if name in class_fragment],
        "authorizationBindings": [item for item in bindings if item["key"] == "authorization"],
        "oauthBindings": [item for item in bindings if item["key"] == "oauth"],
        "methods": _method_details(body, class_fragment),
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
            if module["module_id"] != REQUEST_MODULE_ID:
                continue
            analyses.append({
                "member_path": entry["path"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "module_id": REQUEST_MODULE_ID,
                "analysis": analyze_body(module["body"]),
            })
    return {
        "format": "musicark-yandex-upload-auth-semantics-v1",
        "source": "asar-stage1-request-authorization-semantics",
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
    parser = argparse.ArgumentParser(description="Resolve stage-one authorization expression semantics safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized authorization-semantics report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
