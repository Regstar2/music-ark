"""Recover the upload/config composition topology using webpack module IDs only.

This probe complements V17 hashed def-use analysis. It emits no JavaScript
source, local identifiers or scalar values. The output is limited to numeric
webpack module IDs, member paths/hashes, allowlisted upload/config property names,
direct import/importer relationships and bounded topology paths.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
from typing import Any

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


TARGET_MODULE_IDS = ("12690", "31322", "37558", "7644", "39670", "70204")
TARGET_PAIRS = (
    ("12690", "31322"),
    ("31322", "7644"),
    ("31322", "39670"),
    ("31322", "37558"),
    ("7644", "39670"),
    ("39670", "70204"),
    ("31322", "70204"),
)
ALLOWLISTED_ANCHORS = (
    "loader/upload-url",
    "getUploadUrl",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "getApiPrefixUrl",
    "UgcUploadHttpClient",
)
ALLOWLISTED_PROPERTIES = (
    "customApiPrefixUrl",
    "customApiToken",
    "apiPrefixUrl",
    "prefixUrl",
    "authorization",
    "headers",
    "clientRemoteType",
    "clientSafeConfig",
)


def _reverse_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, targets in graph.items():
        reverse.setdefault(source, set())
        for target in targets:
            reverse[target].add(source)
    return reverse


def _bounded_distances(graph: dict[str, set[str]], start: str, *, max_depth: int = 8) -> dict[str, int]:
    distances = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        depth = distances[node]
        if depth >= max_depth:
            continue
        for child in sorted(graph.get(node, set())):
            if child not in distances:
                distances[child] = depth + 1
                queue.append(child)
    return distances


def _undirected_path(graph: dict[str, set[str]], start: str, target: str, *, max_depth: int = 10) -> list[str] | None:
    reverse = _reverse_graph(graph)
    queue: deque[list[str]] = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        node = path[-1]
        neighbors = set(graph.get(node, set())) | set(reverse.get(node, set()))
        for child in sorted(neighbors):
            if child == target:
                return [*path, child]
            if child not in visited:
                visited.add(child)
                queue.append([*path, child])
    return None


def _common_importers(graph: dict[str, set[str]], left: str, right: str, *, max_depth: int = 8) -> list[dict[str, Any]]:
    reverse = _reverse_graph(graph)
    left_dist = _bounded_distances(reverse, left, max_depth=max_depth)
    right_dist = _bounded_distances(reverse, right, max_depth=max_depth)
    common = set(left_dist) & set(right_dist)
    common.discard(left)
    common.discard(right)
    ranked = sorted(common, key=lambda node: (left_dist[node] + right_dist[node], max(left_dist[node], right_dist[node]), node))
    return [
        {"module_id": node, "distance_to_left": left_dist[node], "distance_to_right": right_dist[node]}
        for node in ranked[:40]
    ]


def topology_report(
    graph: dict[str, set[str]],
    module_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reverse = _reverse_graph(graph)
    targets = []
    for module_id in TARGET_MODULE_IDS:
        metadata = module_metadata.get(module_id, {})
        targets.append(
            {
                "module_id": module_id,
                "present": module_id in graph or module_id in module_metadata or module_id in reverse,
                "direct_imports": sorted(graph.get(module_id, set())),
                "direct_importers": sorted(reverse.get(module_id, set())),
                "anchors": sorted(metadata.get("anchors", set())),
                "properties": sorted(metadata.get("properties", set())),
                "member_paths": sorted(metadata.get("member_paths", set())),
            }
        )

    pair_records = []
    for left, right in TARGET_PAIRS:
        pair_records.append(
            {
                "left": left,
                "right": right,
                "undirected_path": _undirected_path(graph, left, right),
                "common_importers": _common_importers(graph, left, right),
            }
        )
    return {"target_modules": targets, "target_pairs": pair_records}


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
    graph: dict[str, set[str]] = defaultdict(set)
    metadata: dict[str, dict[str, Any]] = defaultdict(lambda: {"anchors": set(), "properties": set(), "member_paths": set()})
    member_hashes: list[dict[str, str]] = []

    for entry in entries:
        if Path(entry["path"]).suffix.lower() != ".js" or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        modules = wiring_probe._extract_modules(text)  # noqa: SLF001
        touched = False
        for module in modules:
            module_id = module["module_id"]
            body = module["body"]
            imports = {item["source_module_id"] for item in wiring_probe._imports(body)}  # noqa: SLF001
            graph[module_id].update(imports)
            anchors = {anchor for anchor in ALLOWLISTED_ANCHORS if anchor in body}
            properties = {prop for prop in ALLOWLISTED_PROPERTIES if prop in body}
            if module_id in TARGET_MODULE_IDS or anchors or properties:
                metadata[module_id]["anchors"].update(anchors)
                metadata[module_id]["properties"].update(properties)
                metadata[module_id]["member_paths"].add(entry["path"])
                touched = True
        if touched:
            member_hashes.append({"path": entry["path"], "member_sha256": hashlib.sha256(raw).hexdigest()})

    topology = topology_report(graph, metadata)
    return {
        "format": "musicark-yandex-upload-runtime-topology-v1",
        "source": "asar-webpack-numeric-topology-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        **topology,
        "touched_members": member_hashes[:300],
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "ordinary_string_values_included": False,
            "raw_identifiers_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover numeric webpack topology around Yandex upload runtime modules.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime topology report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
