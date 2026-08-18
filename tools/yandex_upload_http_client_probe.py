"""Source-free V7 probe for Yandex Music upload HTTP-client configuration.

The probe inspects only selected ASAR members already identified by earlier
research. It emits anchor locations, sanitized URL literals, HTTP header names,
and protocol-related identifiers. It never emits JavaScript source, credential
values, cookies, authorization values, query values, or audio contents.
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


DEFAULT_ANCHORS = (
    "UgcUploadHttpClient",
    "getUploadUrl",
    "uploadFile",
    "loader/upload-url",
    "baseUrl",
    "baseURL",
    "prefixUrl",
    "excludeHeaders",
    "withoutHeaders",
)

_URL_RE = re.compile(r"https?://[^\s\"'`<>]{3,500}", re.IGNORECASE)
_HOST_LITERAL_RE = re.compile(
    r"(?<![A-Za-z0-9.-])(?:[A-Za-z0-9-]+\.)+(?:yandex\.(?:ru|net|com)|yandex-team\.ru)(?::\d+)?(?:/[A-Za-z0-9_./-]*)?",
    re.IGNORECASE,
)
_HEADER_KEY_RE = re.compile(
    r"[\"']((?:authorization|cookie|user-agent|referer|origin|accept(?:-language)?|content-type|x-[A-Za-z0-9-]{1,80}))[\"']\s*:",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]{1,80}\b")
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:oauth\s+[A-Za-z0-9._~+/-]+|bearer\s+[A-Za-z0-9._~+/-]+|token=|secret=|session=|cookie=)",
    re.IGNORECASE,
)
_PROTOCOL_IDENTIFIER_RE = re.compile(
    r"(?:upload|ugc|http|client|header|base|prefix|url|request|retry|exclude|without|music|api)",
    re.IGNORECASE,
)


def _sanitize_url(value: str) -> str | None:
    clean = value.strip().rstrip(",;)}]")
    try:
        parsed = urlsplit(clean)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    # Preserve host/path only. Query and fragment values are never emitted.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _sanitize_host_literal(value: str) -> str | None:
    clean = value.strip().rstrip(",;)}]")
    if _SENSITIVE_VALUE_RE.search(clean):
        return None
    return clean[:300]


def _nearby_structural_data(text: str, start: int, end: int, radius: int) -> dict[str, Any]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    window = text[left:right]

    urls: list[str] = []
    for match in _URL_RE.finditer(window):
        value = _sanitize_url(match.group(0))
        if value and value not in urls:
            urls.append(value)

    hosts: list[str] = []
    for match in _HOST_LITERAL_RE.finditer(window):
        value = _sanitize_host_literal(match.group(0))
        if value and value not in hosts:
            hosts.append(value)

    header_names: list[str] = []
    for match in _HEADER_KEY_RE.finditer(window):
        value = match.group(1).lower()
        if value not in header_names:
            header_names.append(value)

    identifiers: list[str] = []
    for match in _IDENTIFIER_RE.finditer(window):
        value = match.group(0)
        if not _PROTOCOL_IDENTIFIER_RE.search(value):
            continue
        if value not in identifiers:
            identifiers.append(value)

    return {
        "nearby_urls": urls[:40],
        "nearby_host_literals": hosts[:40],
        "nearby_header_names": header_names[:60],
        "nearby_protocol_identifiers": identifiers[:120],
    }


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    anchors: Iterable[str] = DEFAULT_ANCHORS,
    radius: int = 2400,
) -> dict[str, Any]:
    offsets_list = list(dict.fromkeys(int(value) for value in offsets))
    anchors_list = list(dict.fromkeys(str(value) for value in anchors if str(value)))
    data_start, mappings = target_probe.locate_members(path, offsets_list)

    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            item = unique_members.setdefault(
                key,
                {
                    "path": member["path"],
                    "size": member["size"],
                    "absolute_start": member["absolute_start"],
                    "triggering_offsets": [],
                },
            )
            item["triggering_offsets"].append(mapping["offset"])

    members: list[dict[str, Any]] = []
    for member in unique_members.values():
        raw = _read_member(path, member)
        text = raw.decode("utf-8", errors="replace")
        hits: list[dict[str, Any]] = []
        for anchor in anchors_list:
            for match in re.finditer(re.escape(anchor), text, re.IGNORECASE):
                structural = _nearby_structural_data(text, match.start(), match.end(), radius)
                hits.append(
                    {
                        "anchor": anchor,
                        "member_relative_offset": match.start(),
                        "absolute_offset": member["absolute_start"] + match.start(),
                        **structural,
                    }
                )
        members.append(
            {
                **member,
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(raw).hexdigest(),
                "hits": hits[:300],
            }
        )

    return {
        "format": "musicark-yandex-upload-http-client-report-v1",
        "source": "asar-http-client-structural-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "anchors": anchors_list,
        "radius": int(radius),
        "members": members,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "source_code_contexts_included": False,
            "raw_file_contents_included": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract source-free host/header-name structure for the Yandex UGC upload HTTP client."
    )
    parser.add_argument("input", type=Path, help="Path to the official Yandex Music app.asar.")
    parser.add_argument(
        "--offset",
        type=int,
        action="append",
        required=True,
        help="Absolute byte offset selecting a known ASAR member. Repeat as needed.",
    )
    parser.add_argument("--anchor", action="append", default=None, help="Optional anchor override. Repeatable.")
    parser.add_argument("--radius", type=int, default=2400, help="Structural scan radius around each anchor.")
    parser.add_argument("--output", type=Path, required=True, help="Write sanitized JSON report here.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    if args.radius < 200 or args.radius > 20000:
        raise SystemExit("--radius must be between 200 and 20000")
    report = build_report(
        args.input,
        args.offset,
        anchors=args.anchor or DEFAULT_ANCHORS,
        radius=args.radius,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote sanitized V7 HTTP-client report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
