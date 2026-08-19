"""Trace the structural source of ``passportCredentials.host`` safely.

V34 proves stage one derives its prefix from
``this.config.passportCredentials.host``. This probe therefore inspects only
``passportCredentials`` object bindings and their ``host`` property. It emits
stable webpack module/export references, hashed local aliases, normalized
operators and allowlisted Yandex host/template literals. It never emits raw
source, arbitrary strings, credentials, header values or scalar config values.
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
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_target_probe as target_probe


SCHEMA = "passportCredentials"
_TEXT_SUFFIXES = {".js", ".json", ".html", ".htm", ".txt"}
_SENSITIVE_NAME_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|credential|password|signature)",
    re.IGNORECASE,
)
_SAFE_TEMPLATE_RE = re.compile(
    r"^https?://[A-Za-z0-9._:{}$%+\-]*yandex[A-Za-z0-9._:{}$%+\-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+\-]*)?$",
    re.IGNORECASE,
)
_MODULE_TOKEN_RE = re.compile(r"^(?P<prefix>m\d+)\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{0,100})$")


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _safe_template(value: str) -> str | None:
    clean = value.strip()
    if not clean or len(clean) > 300 or "?" in clean or "#" in clean:
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


def _import_refs(expression: str, imports: list[dict[str, str]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for item in imports:
        member_pattern = re.compile(rf"\b{re.escape(item['local'])}\.(?P<member>[A-Za-z_$][A-Za-z0-9_$]{{0,100}})")
        found_member = False
        for match in member_pattern.finditer(expression):
            member = match.group("member")
            if _SENSITIVE_NAME_RE.search(member):
                found_member = True
                continue
            record = {"source_module_id": item["source_module_id"], "export_key": member}
            if record not in results:
                results.append(record)
            found_member = True
        if not found_member and re.search(rf"\b{re.escape(item['local'])}\b", expression):
            record = {"source_module_id": item["source_module_id"], "export_key": "<module-object>"}
            if record not in results:
                results.append(record)
    return results[:80]


def _safe_normalized(module_id: str, expression: str, imports: list[dict[str, str]]) -> list[str]:
    tokens = prefix_probe._normalized_expression(module_id, expression, imports)  # noqa: SLF001
    output: list[str] = []
    for token in tokens:
        match = _MODULE_TOKEN_RE.fullmatch(token)
        if match and _SENSITIVE_NAME_RE.search(match.group("member")):
            output.append(f"{match.group('prefix')}.<redacted-sensitive-member>")
        else:
            output.append(token)
    return output


def _host_record(module_id: str, expression: str, imports: list[dict[str, str]]) -> dict[str, Any]:
    clean = expression.strip()
    semantic_paths: list[list[str]] = []
    for match in re.finditer(
        r"\b(?:this\.)?(?P<base>config|clientSafeConfig)\.(?P<schema>[A-Za-z_$][A-Za-z0-9_$]{0,100})\.host\b",
        re.sub(r"\s+", "", clean).replace("?.", "."),
    ):
        semantic_paths.append([match.group("base"), match.group("schema"), "host"])
    return {
        "safeYandexTemplates": _safe_literals(clean),
        "sourceRefs": _import_refs(clean, imports),
        "semanticPaths": semantic_paths[:20],
        "normalized": _safe_normalized(module_id, clean, imports),
    }


def _schema_object_records(module_id: str, body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    pattern = re.compile(r"(?:[\"']passportCredentials[\"']|\bpassportCredentials\b)\s*:\s*\{")
    for match in pattern.finditer(body):
        start = body.find("{", match.start(), match.end())
        end = contract_probe._find_matching(body, start, "{", "}") if start >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        obj = body[start : end + 1]
        host_rhs = prefix_probe._object_property_rhs(obj, "host")  # noqa: SLF001
        if host_rhs is None:
            continue
        item = {"relation": "object-host", "host": _host_record(module_id, host_rhs, imports)}
        if item not in results:
            results.append(item)
    return results[:80]


def _schema_assignment_records(module_id: str, body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    for pattern in (
        re.compile(r"\bpassportCredentials\.host\s*=\s*(?!=)"),
        re.compile(r"\bthis\.config\.passportCredentials\.host\s*=\s*(?!=)"),
    ):
        for match in pattern.finditer(body):
            rhs = prefix_probe._slice_rhs(body, match.end())  # noqa: SLF001
            if not rhs:
                continue
            item = {"relation": "host-assignment", "host": _host_record(module_id, rhs, imports)}
            if item not in results:
                results.append(item)
    return results[:80]


def analyze_module(module_id: str, body: str) -> dict[str, Any]:
    return {
        "schemaObjects": _schema_object_records(module_id, body),
        "hostAssignments": _schema_assignment_records(module_id, body),
    }


def build_report(path: Path, *, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    modules: list[dict[str, Any]] = []
    for entry in entries:
        if Path(entry["path"]).suffix.lower() not in _TEXT_SUFFIXES or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        if SCHEMA not in text:
            continue
        if entry["path"].endswith(".js"):
            for module in wiring_probe._extract_modules(text):  # noqa: SLF001
                if SCHEMA not in module["body"]:
                    continue
                analysis = analyze_module(module["module_id"], module["body"])
                if analysis["schemaObjects"] or analysis["hostAssignments"]:
                    modules.append({
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        "module_id": module["module_id"],
                        "analysis": analysis,
                    })
    return {
        "format": "musicark-yandex-upload-passport-host-source-v1",
        "source": "asar-passportCredentials-host-structural-provenance",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "modules": modules[:160],
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
    parser = argparse.ArgumentParser(description="Trace passportCredentials.host structural source safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized passport host-source report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
