"""Normalize the exact three arguments passed to stage-one getTldHost.

The report contains only normalized syntax tokens, stable webpack module/export
references, hashed local aliases and the known TLD_MARK relation. It never emits
raw source, arbitrary strings or values.
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
import yandex_upload_target_probe as target_probe


COMPOSITION_MODULE_ID = "7644"
HELPER_MODULE_ID = "91953"


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _find_call(body: str) -> dict[str, Any] | None:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    aliases = [item["local"] for item in imports if item["source_module_id"] == HELPER_MODULE_ID]
    for alias in aliases:
        marker = re.search(rf"{re.escape(alias)}\.getTldHost", body)
        if not marker:
            continue
        open_paren = body.find("(", marker.end())
        if open_paren < 0:
            continue
        # In minified code the function may be wrapped in `(0, fn)`; skip the
        # wrapper close and locate the invocation paren if necessary.
        between = body[marker.end():open_paren]
        if ")" in between:
            open_paren = body.find("(", open_paren + 1)
        end = contract_probe._find_matching(body, open_paren, "(", ")") if open_paren >= 0 else None  # noqa: SLF001
        if end is None:
            continue
        args = contract_probe._split_top_level(body[open_paren + 1:end])  # noqa: SLF001
        if len(args) != 3:
            continue
        return {
            "argumentCount": 3,
            "arguments": [
                {
                    "index": index,
                    "normalized": prefix_probe._normalized_expression(COMPOSITION_MODULE_ID, arg, imports),  # noqa: SLF001
                }
                for index, arg in enumerate(args)
            ],
        }
    return None


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
            call = _find_call(module["body"])
            if call:
                matches.append({
                    "member_path": entry["path"],
                    "member_sha256": hashlib.sha256(raw).hexdigest(),
                    "module_id": COMPOSITION_MODULE_ID,
                    "call": call,
                })
    return {
        "format": "musicark-yandex-upload-prefix-argument-v1",
        "source": "asar-stage1-getTldHost-normalized-arguments",
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
    parser = argparse.ArgumentParser(description="Normalize exact stage-one getTldHost arguments safely.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized prefix-argument report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
