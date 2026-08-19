"""Recover only safe Yandex host templates from the proven stage-one prefix module.

V25 proved ``getTldHost(template, tld, "{tld}")`` semantics structurally. V24
proved that the template argument is sourced from webpack module 32732. This
probe therefore inspects only that module and emits only HTTP(S) literals that
contain ``yandex`` and are composed of host/path characters plus simple
placeholders. Query/fragment data and all other strings are discarded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_prefix_provenance_probe as prefix_probe
import yandex_upload_target_probe as target_probe


PREFIX_MODULE_ID = "32732"
_SAFE_TEMPLATE_RE = re.compile(
    r"^https?://[A-Za-z0-9._:{}$%+\-]*yandex[A-Za-z0-9._:{}$%+\-]*(?::\d+)?(?:/[A-Za-z0-9_./{}:$%+\-]*)?$",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)",
    re.IGNORECASE,
)


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def _safe_template(value: str) -> str | None:
    clean = value.strip()
    if not clean or len(clean) > 300 or "?" in clean or "#" in clean or _SENSITIVE_RE.search(clean):
        return None
    return clean if _SAFE_TEMPLATE_RE.fullmatch(clean) else None


def _templates(body: str) -> list[str]:
    results: list[str] = []
    index = 0
    while index < len(body):
        if body[index] not in {'"', "'", "`"}:
            index += 1
            continue
        value, index = prefix_probe._read_js_string(body, index)  # noqa: SLF001
        safe = _safe_template(value)
        if safe and safe not in results:
            results.append(safe)
    return results[:80]


def _module_export_shape(body: str) -> dict[str, Any]:
    # Report structural export styles only; never emit the RHS or raw local names.
    commonjs_string = bool(re.search(r"\b[A-Za-z_$][A-Za-z0-9_$]*\.exports\s*=\s*[\"'`]", body))
    webpack_named = bool(re.search(r"\b[A-Za-z_$][A-Za-z0-9_$]*\.d\s*\(", body))
    return {"commonJsScalarAssignmentPresent": commonjs_string, "webpackNamedExportsPresent": webpack_named}


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
            if module["module_id"] != PREFIX_MODULE_ID:
                continue
            body = module["body"]
            matches.append({
                "member_path": entry["path"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "module_id": PREFIX_MODULE_ID,
                "exportShape": _module_export_shape(body),
                "safeYandexTemplates": _templates(body),
            })
    return {
        "format": "musicark-yandex-upload-prefix-template-v1",
        "source": "asar-proven-stage1-prefix-template-scan",
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
    parser = argparse.ArgumentParser(description="Recover the safe Yandex stage-one prefix template.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit("Input app.asar does not exist")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one prefix-template report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
