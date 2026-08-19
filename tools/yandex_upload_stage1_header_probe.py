"""Recover value-free provenance for observed official stage-one header names.

The probe scans the official desktop ASAR offline. It emits only allowlisted
header names, semantic identifier names, webpack module IDs/export keys, hashed
local aliases and numeric dependency paths from the stage-one upload module.
Header values, source code, credentials, cookies and ordinary strings are never
emitted.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_stage1_flow_probe as flow_probe
import yandex_upload_target_probe as target_probe


_STAGE1_MODULE_ID = "12690"
_HEADERS = (
    "authorization",
    "accept-language",
    "x-yandex-music-client",
    "x-request-id",
    "x-yandex-music-device",
    "x-yandex-music-without-invocation-info",
)
_ANCHORS = (
    "createRequestHeaders",
    "createHttpOptions",
    "common",
    "oauth",
    "language",
    "client",
    "device",
    "requestId",
    "withoutInvocationInfo",
    "clientRemoteType",
    "YandexMusicDesktopApp",
)


def _header_bindings(module_id: str, body: str) -> list[dict[str, Any]]:
    imports = wiring_probe._imports(body)  # noqa: SLF001
    results: list[dict[str, Any]] = []
    for header in _HEADERS:
        pattern = re.compile(rf"[\"']{re.escape(header)}[\"']\s*:\s*", re.IGNORECASE)
        for match in pattern.finditer(body):
            rhs = flow_probe._slice_rhs(body, match.end(), limit=len(body))  # noqa: SLF001
            summary = flow_probe._summary(  # noqa: SLF001
                module_id,
                rhs,
                imports,
                body=body,
                before=match.start(),
            )
            record = {"header": header, "value": summary}
            if record not in results:
                results.append(record)
    return results[:120]


def _module_report(module_id: str, body: str) -> dict[str, Any] | None:
    bindings = _header_bindings(module_id, body)
    literal_headers = [header for header in _HEADERS if re.search(rf"[\"']{re.escape(header)}[\"']", body, re.IGNORECASE)]
    if not bindings and not literal_headers:
        return None
    return {
        "module_id": module_id,
        "headersPresent": sorted(literal_headers),
        "anchorsPresent": [anchor for anchor in _ANCHORS if re.search(rf"\b{re.escape(anchor)}\b", body)],
        "headerBindings": bindings,
    }


def _shortest_path(graph: dict[str, set[str]], start: str, target: str, *, max_depth: int = 8) -> list[str] | None:
    if start == target:
        return [start]
    queue: deque[list[str]] = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for child in sorted(graph.get(path[-1], set())):
            if child == target:
                return [*path, child]
            if child not in visited:
                visited.add(child)
                queue.append([*path, child])
    return None


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
    graph: dict[str, set[str]] = defaultdict(set)

    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        for module in wiring_probe._extract_modules(text):  # noqa: SLF001
            module_id = module["module_id"]
            imports = wiring_probe._imports(module["body"])  # noqa: SLF001
            graph[module_id].update(item["source_module_id"] for item in imports)
            report = _module_report(module_id, module["body"])
            if report is not None:
                modules.append(
                    {
                        "member_path": entry["path"],
                        "member_sha256": hashlib.sha256(raw).hexdigest(),
                        **report,
                    }
                )

    dependency_paths: list[dict[str, Any]] = []
    for module in modules:
        path_ids = _shortest_path(graph, _STAGE1_MODULE_ID, module["module_id"])
        if path_ids:
            dependency_paths.append(
                {
                    "from_module_id": _STAGE1_MODULE_ID,
                    "to_module_id": module["module_id"],
                    "headersPresent": module["headersPresent"],
                    "path": path_ids,
                }
            )

    return {
        "format": "musicark-yandex-upload-stage1-header-provenance-v1",
        "source": "asar-stage1-header-semantic-provenance",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "modules": modules[:240],
        "stage1DependencyPaths": dependency_paths[:160],
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
    parser = argparse.ArgumentParser(description="Recover secret-free provenance for successful desktop stage-one headers.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized stage-one header provenance report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
