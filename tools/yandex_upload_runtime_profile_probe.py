"""Source-free probe for the public Yandex Music desktop upload HTTP profile.

The probe reports only sanitized Yandex URLs, public client/profile names,
header names, webpack module IDs, allowlisted upload/config anchors, numeric
module dependency paths, and allowlisted configuration property names. It never
emits JavaScript source, arbitrary strings, query values, credentials, cookies,
authorization values, raw ASAR bytes, or audio.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yandex_upload_module_wiring_probe as wiring_probe
import yandex_upload_target_probe as target_probe


ANCHORS = (
    "loader/upload-url",
    "getUploadUrl",
    "UgcUploadHttpClient",
    "getApiPrefixUrl",
    "customApiPrefixUrl",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "clientRemoteType",
    "clientSafeConfig",
    "getClientSafeConfig",
    "prefixUrl",
)
MODULE_ANCHORS = (
    "loader/upload-url",
    "getUploadUrl",
    "UgcUploadHttpClient",
    "getApiPrefixUrl",
    "customApiPrefixUrl",
    "customApiToken",
    "createHttpOptions",
    "createRequestHeaders",
    "createSessionRequestHeaders",
    "clientRemoteType",
    "YandexMusicDesktopApp",
    "YandexMusicWebNext",
)
MODULE_PROPERTIES = (
    "prefixUrl",
    "apiPrefixUrl",
    "customApiPrefixUrl",
    "token",
    "apiToken",
    "customApiToken",
    "clientRemoteType",
    "headers",
    "authorization",
    "userAgent",
)
PUBLIC_CLIENT_LITERALS = ("YandexMusicDesktopApp", "YandexMusicWebNext")
_HEADER_NAMES = {
    "user-agent",
    "authorization",
    "accept",
    "accept-language",
    "content-type",
    "origin",
    "referer",
    "x-yandex-music-client",
    "x-retry-count",
}
_TEXT_SUFFIXES = {".js", ".json", ".html", ".htm", ".txt", ".map"}
_URL_RE = re.compile(r"https?://[^\s\"'`<>]{3,500}", re.IGNORECASE)
_QUOTED_HEADER_RE = re.compile(r"[\"'](?P<name>[A-Za-z0-9-]{1,80})[\"']\s*:", re.IGNORECASE)
_DIRECT_URL_BINDING_RE = re.compile(
    r"(?P<key>apiPrefixUrl|customApiPrefixUrl|prefixUrl|baseUrl|baseURL)"
    r"\s*:\s*(?P<quote>[\"'`])(?P<url>https?://[^\"'`]{3,500})(?P=quote)",
    re.IGNORECASE,
)
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|credential|password|signature)",
    re.IGNORECASE,
)


def _is_text_member(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in _TEXT_SUFFIXES and not path.endswith(".min.js.map")


def _is_yandex_host(host: str) -> bool:
    clean = host.lower().split(":", 1)[0].rstrip(".")
    return any(clean == suffix or clean.endswith(f".{suffix}") for suffix in ("yandex.ru", "yandex.net", "yandex.com"))


def _sanitize_yandex_url(value: str) -> str | None:
    clean = value.strip().rstrip(",;)}]")
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not _is_yandex_host(parsed.netloc):
        return None
    if _SENSITIVE_RE.search(f"{parsed.netloc}{parsed.path}"):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))


def _safe_header_names(text: str) -> list[str]:
    found: list[str] = []
    for match in _QUOTED_HEADER_RE.finditer(text):
        name = match.group("name").lower()
        if name in _HEADER_NAMES and name not in found:
            found.append(name)
    return found


def _public_clients(text: str) -> list[str]:
    return [value for value in PUBLIC_CLIENT_LITERALS if value in text]


def _url_occurrences(text: str) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for match in _URL_RE.finditer(text):
        url = _sanitize_yandex_url(match.group(0))
        if url and (match.start(), url) not in results:
            results.append((match.start(), url))
    return results


def _direct_bindings(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in _DIRECT_URL_BINDING_RE.finditer(text):
        url = _sanitize_yandex_url(match.group("url"))
        if url:
            item = {"key": match.group("key"), "url": url}
            if item not in results:
                results.append(item)
    return results[:80]


def _anchor_records(text: str, urls: list[tuple[int, str]], radius: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for anchor in ANCHORS:
        for match in re.finditer(re.escape(anchor), text, re.IGNORECASE):
            left = max(0, match.start() - radius)
            right = min(len(text), match.end() + radius)
            window = text[left:right]
            candidates = [
                {"url": url, "distance": abs(position - match.start())}
                for position, url in urls
                if left <= position <= right
            ]
            candidates.sort(key=lambda item: (item["distance"], item["url"]))
            records.append(
                {
                    "anchor": anchor,
                    "member_relative_offset": match.start(),
                    "nearby_urls": candidates[:20],
                    "public_clients": _public_clients(window),
                    "header_names": _safe_header_names(window),
                }
            )
    return records[:400]


def _module_properties(body: str) -> list[str]:
    """Return only allowlisted property names, never their base/value/context."""
    found: list[str] = []
    for name in MODULE_PROPERTIES:
        patterns = (
            rf"\.{re.escape(name)}\b",
            rf"[\"']{re.escape(name)}[\"']\s*:",
            rf"(?<![A-Za-z0-9_$]){re.escape(name)}\s*:",
        )
        if any(re.search(pattern, body) for pattern in patterns):
            found.append(name)
    return found


def _module_structure(text: str) -> tuple[list[dict[str, Any]], dict[str, set[str]], dict[str, list[str]]]:
    sets: list[dict[str, Any]] = []
    graph: dict[str, set[str]] = defaultdict(set)
    properties: dict[str, list[str]] = {}
    for module in wiring_probe._extract_modules(text):  # noqa: SLF001
        body = module["body"]
        module_id = module["module_id"]
        graph[module_id].update(item["source_module_id"] for item in wiring_probe._imports(body))  # noqa: SLF001
        props = _module_properties(body)
        if props:
            properties[module_id] = props
        anchors = [anchor for anchor in MODULE_ANCHORS if anchor in body]
        if anchors:
            sets.append({"module_id": module_id, "anchors": anchors})
    return sets[:240], graph, properties


def _module_anchor_sets(text: str) -> list[dict[str, Any]]:
    return _module_structure(text)[0]


def _shortest_path(graph: dict[str, set[str]], start: str, target: str, max_depth: int = 6) -> list[str] | None:
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


def _dependency_paths(graph: dict[str, set[str]], anchor_sets: list[dict[str, Any]], *, max_depth: int = 6) -> list[dict[str, Any]]:
    loader_ids = sorted({item["module_id"] for item in anchor_sets if "loader/upload-url" in item["anchors"]})
    targets = [
        item
        for item in anchor_sets
        if any(
            anchor in item["anchors"]
            for anchor in (
                "getApiPrefixUrl",
                "createRequestHeaders",
                "createSessionRequestHeaders",
                "clientRemoteType",
                "YandexMusicDesktopApp",
                "YandexMusicWebNext",
                "customApiPrefixUrl",
                "customApiToken",
            )
        )
    ]
    results: list[dict[str, Any]] = []
    for loader_id in loader_ids:
        for target in targets:
            path = _shortest_path(graph, loader_id, target["module_id"], max_depth=max_depth)
            if path is None:
                continue
            item = {
                "from_module_id": loader_id,
                "to_module_id": target["module_id"],
                "target_anchors": target["anchors"],
                "path": path,
            }
            if item not in results:
                results.append(item)
    return results[:160]


def _dependency_module_properties(paths: list[dict[str, Any]], properties: dict[str, set[str]]) -> list[dict[str, Any]]:
    relevant_ids = sorted({module_id for item in paths for module_id in item["path"]})
    return [
        {"module_id": module_id, "properties": sorted(properties.get(module_id, set()))}
        for module_id in relevant_ids
        if properties.get(module_id)
    ]


def _read_member(path: Path, entry: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(entry["start"])
        data = stream.read(entry["size"])
    if len(data) != entry["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {entry['path']}")
    return data


def build_report(path: Path, *, radius: int = 12000, max_member_size: int = 8_000_000) -> dict[str, Any]:
    header, data_start = target_probe.read_asar_header(path)
    entries = list(target_probe._walk_entries(header["files"], data_start=data_start))  # noqa: SLF001
    members: list[dict[str, Any]] = []
    candidate_urls: dict[str, dict[str, Any]] = {}
    all_module_sets: list[dict[str, Any]] = []
    aggregate_graph: dict[str, set[str]] = defaultdict(set)
    aggregate_properties: dict[str, set[str]] = defaultdict(set)

    for entry in entries:
        if not _is_text_member(entry["path"]) or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        urls = _url_occurrences(text)
        direct_bindings = _direct_bindings(text)
        module_sets: list[dict[str, Any]] = []
        if entry["path"].endswith(".js"):
            module_sets, member_graph, member_properties = _module_structure(text)
            for module_id, imports in member_graph.items():
                aggregate_graph[module_id].update(imports)
            for module_id, props in member_properties.items():
                aggregate_properties[module_id].update(props)

        lowered = text.lower()
        present_anchors = [anchor for anchor in ANCHORS if anchor.lower() in lowered]
        if not present_anchors and not direct_bindings and not module_sets:
            continue
        anchor_records = _anchor_records(text, urls, radius)
        members.append(
            {
                "path": entry["path"],
                "size": entry["size"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "anchors_present": present_anchors,
                "direct_url_bindings": direct_bindings,
                "yandex_urls": sorted({url for _, url in urls})[:200],
                "public_clients": _public_clients(text),
                "header_names": _safe_header_names(text),
                "anchor_records": anchor_records,
                "webpack_module_anchor_sets": module_sets,
            }
        )
        for module_set in module_sets:
            all_module_sets.append({"member_path": entry["path"], **module_set})
        for record in anchor_records:
            for candidate in record["nearby_urls"]:
                url = candidate["url"]
                evidence = {
                    "url": url,
                    "best_distance": candidate["distance"],
                    "member_path": entry["path"],
                    "nearest_anchor": record["anchor"],
                }
                current = candidate_urls.get(url)
                if current is None or evidence["best_distance"] < current["best_distance"]:
                    candidate_urls[url] = evidence
        for binding in direct_bindings:
            url = binding["url"]
            direct = {
                "url": url,
                "best_distance": 0,
                "member_path": entry["path"],
                "nearest_anchor": f"direct:{binding['key']}",
            }
            current = candidate_urls.get(url)
            if current is None or current["best_distance"] > 0:
                candidate_urls[url] = direct

    dependency_paths = _dependency_paths(aggregate_graph, all_module_sets)
    ranked = sorted(candidate_urls.values(), key=lambda item: (item["best_distance"], item["url"]))
    return {
        "format": "musicark-yandex-upload-runtime-profile-report-v4",
        "source": "asar-public-runtime-profile-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "radius": radius,
        "members": members[:300],
        "webpack_module_anchor_sets": all_module_sets[:500],
        "webpack_dependency_paths": dependency_paths,
        "dependency_module_properties": _dependency_module_properties(dependency_paths, aggregate_properties),
        "ranked_yandex_url_candidates": ranked[:120],
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "ordinary_string_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover public/non-secret Yandex desktop upload HTTP profile evidence.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--radius", type=int, default=12000)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    if args.radius < 500 or args.radius > 50000:
        raise SystemExit("--radius must be between 500 and 50000")
    report = build_report(args.input, radius=args.radius)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized runtime-profile report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
