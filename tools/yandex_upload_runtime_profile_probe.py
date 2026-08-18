"""Source-free probe for the public Yandex Music desktop upload HTTP profile.

The probe answers one narrow question: which non-secret Yandex host/prefix and
public client-profile literals are structurally associated with the desktop
HTTP configuration used around the recovered UGC upload pipeline.

It scans only text-like packed members from the locally installed official
``app.asar`` and emits sanitized Yandex URLs (scheme/host/path only), safe
configuration key names, public client enum literals, header names, and anchor
proximity. It never emits JavaScript source, arbitrary string values, query
values, credentials, cookies, authorization values, raw ASAR bytes, or audio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

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
CONFIG_KEYS = (
    "apiPrefixUrl",
    "customApiPrefixUrl",
    "prefixUrl",
    "baseUrl",
    "baseURL",
)
PUBLIC_CLIENT_LITERALS = (
    "YandexMusicDesktopApp",
    "YandexMusicWebNext",
)
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
_QUOTED_HEADER_RE = re.compile(
    r"[\"'](?P<name>[A-Za-z0-9-]{1,80})[\"']\s*:",
    re.IGNORECASE,
)
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
    return clean == "yandex.ru" or clean.endswith(".yandex.ru") or clean == "yandex.net" or clean.endswith(".yandex.net") or clean == "yandex.com" or clean.endswith(".yandex.com")


def _sanitize_yandex_url(value: str) -> str | None:
    clean = value.strip().rstrip(",;)}]")
    if _SENSITIVE_RE.search(clean):
        return None
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not _is_yandex_host(parsed.netloc):
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
        key = match.group("key")
        url = _sanitize_yandex_url(match.group("url"))
        if not url:
            continue
        item = {"key": key, "url": url}
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
            record = {
                "anchor": anchor,
                "member_relative_offset": match.start(),
                "nearby_urls": candidates[:20],
                "public_clients": _public_clients(window),
                "header_names": _safe_header_names(window),
            }
            records.append(record)
    return records[:400]


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
    for entry in entries:
        if not _is_text_member(entry["path"]) or entry["size"] <= 0 or entry["size"] > max_member_size:
            continue
        raw = _read_member(path, entry)
        text = raw.decode("utf-8", errors="replace")
        present_anchors = [anchor for anchor in ANCHORS if anchor.lower() in text.lower()]
        direct_bindings = _direct_bindings(text)
        urls = _url_occurrences(text)
        if not present_anchors and not direct_bindings:
            continue

        anchor_records = _anchor_records(text, urls, radius)
        member_urls = sorted({url for _, url in urls})[:200]
        public_clients = _public_clients(text)
        header_names = _safe_header_names(text)
        members.append(
            {
                "path": entry["path"],
                "size": entry["size"],
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "anchors_present": present_anchors,
                "direct_url_bindings": direct_bindings,
                "yandex_urls": member_urls,
                "public_clients": public_clients,
                "header_names": header_names,
                "anchor_records": anchor_records,
            }
        )

        for record in anchor_records:
            for candidate in record["nearby_urls"]:
                url = candidate["url"]
                current = candidate_urls.get(url)
                evidence = {
                    "member_path": entry["path"],
                    "anchor": record["anchor"],
                    "distance": candidate["distance"],
                }
                if current is None or evidence["distance"] < current["best_distance"]:
                    candidate_urls[url] = {
                        "url": url,
                        "best_distance": evidence["distance"],
                        "member_path": evidence["member_path"],
                        "nearest_anchor": evidence["anchor"],
                    }

        for binding in direct_bindings:
            url = binding["url"]
            current = candidate_urls.get(url)
            direct = {
                "url": url,
                "best_distance": 0,
                "member_path": entry["path"],
                "nearest_anchor": f"direct:{binding['key']}",
            }
            if current is None or current["best_distance"] > 0:
                candidate_urls[url] = direct

    ranked = sorted(
        candidate_urls.values(),
        key=lambda item: (item["best_distance"], item["url"]),
    )
    return {
        "format": "musicark-yandex-upload-runtime-profile-report-v1",
        "source": "asar-public-runtime-profile-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "radius": radius,
        "members": members[:300],
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
