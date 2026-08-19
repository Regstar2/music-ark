"""Call-site focused, offline probe for Yandex Music UGC upload research.

This tool narrows a previously identified ASAR member down to small windows
around selected upload-related identifiers. It emits only the sanitized
structural representation produced by ``yandex_upload_target_probe`` and never
emits raw JavaScript source, ordinary string values, credentials, cookies, or
file contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yandex_upload_target_probe as target_probe


DEFAULT_NAMES = (
    "getUploadUrl",
    "uploadFile",
    "runUpload",
    "retryUpload",
    "abortUpload",
    "checkProcessingTracks",
    "moveTracksFromUploadCenterToPlaylist",
)


def analyze_member_text(
    text: str,
    *,
    names: Iterable[str] = DEFAULT_NAMES,
    radius: int = 1800,
) -> list[dict[str, Any]]:
    """Return safe structural windows around selected identifier occurrences."""
    sites: list[dict[str, Any]] = []
    encoded = text.encode("utf-8", errors="replace")

    # Work in character offsets for matching because the minified bundle is UTF-8
    # text; hashes are only used as stable local identifiers and never as offsets.
    for name in dict.fromkeys(names):
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        for occurrence, match in enumerate(pattern.finditer(text), start=1):
            left = max(0, match.start() - radius)
            right = min(len(text), match.end() + radius)
            window = text[left:right]
            window_bytes = window.encode("utf-8", errors="replace")
            structure = target_probe.extract_structure(window)
            sites.append(
                {
                    "name": name,
                    "occurrence": occurrence,
                    "position": match.start(),
                    "window": {
                        "start": left,
                        "end": right,
                        "sha256_16": hashlib.sha256(window_bytes).hexdigest()[:16],
                        "structure": structure,
                    },
                }
            )

    # Avoid retaining a second copy of the source in memory longer than needed.
    del encoded
    return sites


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise target_probe.AsarFormatError(
            f"Unable to read complete ASAR member: {member['path']}"
        )
    return data


def build_report(
    path: Path,
    offsets: Iterable[int],
    *,
    names: Iterable[str] = DEFAULT_NAMES,
    radius: int = 1800,
) -> dict[str, Any]:
    """Build a call-site report for ASAR members containing selected offsets."""
    offset_list = list(dict.fromkeys(int(offset) for offset in offsets))
    name_list = list(dict.fromkeys(str(name) for name in names if str(name)))
    data_start, mappings = target_probe.locate_members(path, offset_list)

    unique_members: dict[tuple[str, int], dict[str, Any]] = {}
    for mapping in mappings:
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            existing = unique_members.setdefault(
                key,
                {
                    "path": member["path"],
                    "size": member["size"],
                    "absolute_start": member["absolute_start"],
                    "triggering_offsets": [],
                },
            )
            existing["triggering_offsets"].append(mapping["offset"])

    members: list[dict[str, Any]] = []
    for member in unique_members.values():
        member_bytes = _read_member(path, member)
        member_text = member_bytes.decode("utf-8", errors="replace")
        call_sites = analyze_member_text(member_text, names=name_list, radius=radius)
        members.append(
            {
                **member,
                "triggering_offsets": sorted(set(member["triggering_offsets"])),
                "member_sha256": hashlib.sha256(member_bytes).hexdigest(),
                "call_site_count": len(call_sites),
                "call_sites": call_sites,
            }
        )

    return {
        "format": "musicark-yandex-upload-callsite-report-v1",
        "source": "asar-callsite-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "radius": radius,
        "names": name_list,
        "members": members,
        "safety": {
            "network_requests_sent": False,
            "credential_values_included": False,
            "source_code_contexts_included": False,
            "ordinary_string_values_included": False,
            "raw_file_contents_included": False,
        },
    }


def _write_report(report: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if output is None:
        print(encoded)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(f"Wrote call-site sanitized report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect safe structural windows around Yandex Music upload call sites "
            "inside ASAR members selected by known byte offsets."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the official Yandex Music app.asar.")
    parser.add_argument(
        "--offset",
        type=int,
        action="append",
        required=True,
        help="Absolute byte offset from a prior static report. Repeat as needed.",
    )
    parser.add_argument(
        "--name",
        action="append",
        default=None,
        help="Identifier to inspect. Repeat to override the default upload-related names.",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=1800,
        help="Characters to inspect on each side of every identifier occurrence.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report instead of stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    if args.radius < 256 or args.radius > 16384:
        raise SystemExit("--radius must be between 256 and 16384")

    report = build_report(
        args.input,
        args.offset,
        names=args.name or DEFAULT_NAMES,
        radius=args.radius,
    )
    _write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
