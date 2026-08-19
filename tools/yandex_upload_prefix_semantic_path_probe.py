"""Resolve the semantic config path used by stage-one getTldHost.

The exact stage-one call is already proven to pass an expression shaped like
``this.config.<property>.host`` and ``this.tld``. Property names on this exact
configuration path are schema names, not scalar values, and may be emitted even
when their names contain words such as ``token``. No property value, credential,
header value or source context is included.
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
import yandex_upload_target_probe as target_probe


MODULE_ID = "7644"
HELPER_MODULE_ID = "91953"
_SAFE_PROPERTY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,100}$")


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _call_args(body: str) -> list[str] | None:
    for item in wiring_probe._imports(body):  # noqa: SLF001
        if item["source_module_id"] != HELPER_MODULE_ID:
            continue
        marker = re.search(rf"{re.escape(item['local'])}\.getTldHost", body)
        if not marker:
            continue
        open_paren = body.find("(", marker.end())
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = [part.strip() for part in contract_probe._split_top_level(body[open_paren + 1:end])]  # noqa: SLF001
        if len(args) == 3:
            return args
    return None


def _safe_chain(expression: str) -> list[str] | None:
    clean = re.sub(r"\s+", "", expression).replace("?.", ".")
    clean = re.sub(r"\[['\"]([A-Za-z_$][A-Za-z0-9_$]{0,100})['\"]\]", r".\1", clean)
    while clean.startswith("(") and clean.endswith(")"):
        clean = clean[1:-1]
    if not clean.startswith("this."):
        return None
    parts = clean.split(".")
    if parts[0] != "this" or len(parts) < 2:
        return None
    if not all(_SAFE_PROPERTY_RE.fullmatch(part) for part in parts[1:]):
        return None
    return parts


def _semantic_config_host_path(expression: str) -> list[str] | None:
    direct = _safe_chain(expression)
    if direct and len(direct) >= 4 and direct[1] == "config" and direct[-1] == "host":
        return direct

    # Handle TypeScript/Babel optional-chain lowering while emitting only the
    # exact static config schema key and the terminal host property.
    compact = re.sub(r"\s+", "", expression).replace("?.", ".")
    matches = re.findall(r"this\.config\.([A-Za-z_$][A-Za-z0-9_$]{0,100})", compact)
    if not matches:
        return None
    unique = list(dict.fromkeys(matches))
    if len(unique) != 1:
        return None
    key = unique[0]
    # Ground the terminal relation either through the direct source expression
    # or a temporary `.host` access used by the lowering.
    if ".host" not in compact:
        return None
    return ["this", "config", key, "host"]


def analyze_body(body: str) -> dict[str, Any]:
    args = _call_args(body)
    if not args:
        return {"callFound": False}
    host_path = _semantic_config_host_path(args[0])
    tld_path = _safe_chain(args[1])
    host_shape_valid = bool(host_path and len(host_path) >= 4 and host_path[1] == "config" and host_path[-1] == "host")
    tld_shape_valid = tld_path == ["this", "tld"]
    return {
        "callFound": True,
        "hostConfigPath": host_path if host_shape_valid else None,
        "tldPath": tld_path if tld_shape_valid else None,
        "hostShapeValid": host_shape_valid,
        "tldShapeValid": tld_shape_valid,
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
            if module["module_id"] == MODULE_ID:
                matches.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": MODULE_ID,
                    "analysis": analyze_body(module["body"]),
                })
    return {
        "format": "musicark-yandex-upload-prefix-semantic-path-v2",
        "source": "asar-stage1-prefix-semantic-config-path",
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
    parser = argparse.ArgumentParser(description="Resolve semantic stage-one prefix config path safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized prefix semantic-path report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
