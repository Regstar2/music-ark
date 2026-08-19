"""Targeted, offline ASAR probe for Yandex Music UGC upload research.

The probe maps raw offsets from the broad binary scan back to files inside an
Electron ASAR archive and emits protocol structure only. It never performs
network I/O and never emits raw source context, ordinary string values, audio
bytes, credential values, cookies, or authorization values.

The ASAR reader follows the public Electron ASAR format: an 8-byte Pickle with
the header Pickle size, then the header Pickle, followed by packed file bytes.
File offsets stored in the JSON header are relative to the packed-file area.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_PROTOCOL_TERMS = (
    "upload",
    "ugc",
    "track",
    "playlist",
    "file",
    "audio",
    "multipart",
    "processing",
    "retry",
    "abort",
)
_NAMED_CALLS = (
    "getUploadUrl",
    "uploadFile",
    "runUpload",
    "runUploadTracksQueue",
    "retryUpload",
    "abortUpload",
    "getUploadingTracksByPlaylistKind",
    "moveTracksFromUploadCenterToPlaylist",
    "checkProcessingTracks",
)
_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|session|csrf|xsrf|passport|sign(?:ature)?|credential)",
    re.IGNORECASE,
)
_QUOTED_RE = re.compile(
    r'''(?P<quote>["'`])(?P<value>(?:\\.|(?!\1).){1,320}?)(?P=quote)''',
    re.DOTALL,
)
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_FORM_APPEND_RE = re.compile(
    r"\.append\(\s*[\"']([A-Za-z0-9_.:-]{1,80})[\"']\s*,",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]{1,100}\b")
_HTTP_CALL_RE = re.compile(
    r"(?:this\.)?httpClient\.(get|post|put|patch|delete)\s*\(\s*"
    r"(?:(?P<quote>[\"'`])(?P<literal>(?:\\.|(?!\2).){1,320}?)(?P=quote)|"
    r"(?P<identifier>[A-Za-z_$][A-Za-z0-9_$]*))",
    re.IGNORECASE | re.DOTALL,
)
_OBJECT_KEY_RE = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]{1,80})\s*:")
_MIME_RE = re.compile(
    r"\b(?:multipart/form-data|application/octet-stream|audio/(?:mpeg|mp4|ogg|opus|wav|x-wav|flac|aac))\b",
    re.IGNORECASE,
)
_AUDIO_EXTENSION_RE = re.compile(r"\.(?:mp3|flac|m4a|ogg|opus|wav|aac)\b", re.IGNORECASE)


class AsarFormatError(ValueError):
    """Raised when the small ASAR index reader cannot validate an archive."""


def _align4(value: int) -> int:
    return value + ((4 - (value % 4)) % 4)


def _pickle_payload_offset(buffer: bytes) -> int:
    if len(buffer) < 4:
        raise AsarFormatError("Pickle buffer is too small")
    payload_size = struct.unpack_from("<I", buffer, 0)[0]
    header_size = len(buffer) - payload_size
    if header_size < 4 or header_size > len(buffer) or header_size % 4 != 0:
        raise AsarFormatError("Invalid Pickle header size")
    return header_size


def _read_pickle_uint32(buffer: bytes) -> int:
    payload_offset = _pickle_payload_offset(buffer)
    if payload_offset + 4 > len(buffer):
        raise AsarFormatError("Pickle does not contain UInt32")
    return struct.unpack_from("<I", buffer, payload_offset)[0]


def _read_pickle_string(buffer: bytes) -> str:
    payload_offset = _pickle_payload_offset(buffer)
    if payload_offset + 4 > len(buffer):
        raise AsarFormatError("Pickle does not contain string length")
    length = struct.unpack_from("<i", buffer, payload_offset)[0]
    if length < 0:
        raise AsarFormatError("Negative Pickle string length")
    start = payload_offset + 4
    end = start + length
    if end > len(buffer):
        raise AsarFormatError("Pickle string extends beyond header")
    return buffer[start:end].decode("utf-8")


def read_asar_header(path: Path) -> tuple[dict[str, Any], int]:
    """Return parsed ASAR header and absolute start of packed file data."""
    archive_size = path.stat().st_size
    with path.open("rb") as stream:
        size_pickle = stream.read(8)
        if len(size_pickle) != 8:
            raise AsarFormatError("Unable to read ASAR header-size Pickle")
        header_pickle_size = _read_pickle_uint32(size_pickle)
        if header_pickle_size <= 0 or header_pickle_size > archive_size - 8:
            raise AsarFormatError("ASAR header size is outside archive bounds")
        header_pickle = stream.read(header_pickle_size)
        if len(header_pickle) != header_pickle_size:
            raise AsarFormatError("Unable to read complete ASAR header")

    raw_header = _read_pickle_string(header_pickle)
    parsed = json.loads(raw_header)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("files"), dict):
        raise AsarFormatError("ASAR root header has no files object")
    return parsed, 8 + header_pickle_size


def _walk_entries(
    files: dict[str, Any],
    *,
    data_start: int,
    prefix: str = "",
) -> Iterable[dict[str, Any]]:
    for name, entry in files.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        member_path = f"{prefix}/{name}" if prefix else name
        children = entry.get("files")
        if isinstance(children, dict):
            yield from _walk_entries(children, data_start=data_start, prefix=member_path)
            continue
        if entry.get("unpacked") is True or "offset" not in entry:
            continue
        try:
            relative_offset = int(str(entry["offset"]))
            size = int(entry.get("size", 0))
        except (TypeError, ValueError):
            continue
        if relative_offset < 0 or size < 0:
            continue
        start = data_start + relative_offset
        yield {
            "path": member_path,
            "start": start,
            "end": start + size,
            "size": size,
        }


def locate_members(path: Path, offsets: Iterable[int]) -> tuple[int, list[dict[str, Any]]]:
    """Map absolute archive offsets to packed ASAR members."""
    header, data_start = read_asar_header(path)
    entries = list(_walk_entries(header["files"], data_start=data_start))
    results: list[dict[str, Any]] = []
    for target in offsets:
        matches = [entry for entry in entries if entry["start"] <= target < entry["end"]]
        results.append(
            {
                "offset": target,
                "members": [
                    {
                        "path": entry["path"],
                        "size": entry["size"],
                        "absolute_start": entry["start"],
                        "relative_offset": target - entry["start"],
                    }
                    for entry in matches
                ],
            }
        )
    return data_start, results


def _sanitize_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<invalid-url>"
    query = urlencode(
        [(name, "<redacted>") for name, _ in parse_qsl(parts.query, keep_blank_values=True)]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _safe_protocol_literal(value: str) -> str | None:
    """Return only protocol-like literals; reject secrets and ordinary strings."""
    if not value or len(value) > 320 or _SENSITIVE_RE.search(value):
        return None
    lowered = value.lower()
    if not any(term in lowered for term in _PROTOCOL_TERMS):
        return None
    if _URL_RE.match(value):
        return _sanitize_url(value)
    if value.startswith("/"):
        # Do not preserve query values from relative URLs either.
        path, separator, query = value.partition("?")
        if not separator:
            return path
        names = []
        for item in query.split("&"):
            name = item.split("=", 1)[0].strip()
            if name and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", name):
                names.append(f"{name}=<redacted>")
        return path + ("?" + "&".join(names) if names else "")
    if re.fullmatch(r"[A-Za-z0-9_./:${}-]{1,160}", value):
        return value
    return None


def extract_structure(text: str) -> dict[str, Any]:
    """Extract protocol structure without returning raw source context."""
    literals: list[str] = []
    for match in _QUOTED_RE.finditer(text):
        safe = _safe_protocol_literal(match.group("value"))
        if safe and safe not in literals:
            literals.append(safe)

    identifiers = sorted(
        {
            identifier
            for identifier in _IDENTIFIER_RE.findall(text)
            if any(term in identifier.lower() for term in _PROTOCOL_TERMS)
            and not _SENSITIVE_RE.search(identifier)
        }
    )[:200]
    form_fields = sorted({match.group(1) for match in _FORM_APPEND_RE.finditer(text)})
    mime_types = sorted({match.group(0).lower() for match in _MIME_RE.finditer(text)})
    extensions = sorted({match.group(0).lower() for match in _AUDIO_EXTENSION_RE.finditer(text)})

    object_keys = sorted(
        {
            key
            for key in _OBJECT_KEY_RE.findall(text)
            if (
                any(term in key.lower() for term in _PROTOCOL_TERMS)
                or key in {"body", "json", "searchParams", "headers", "method", "url"}
            )
            and not _SENSITIVE_RE.search(key)
        }
    )[:160]

    http_calls: list[dict[str, str]] = []
    for match in _HTTP_CALL_RE.finditer(text):
        method = match.group(1).upper()
        literal = match.group("literal")
        identifier = match.group("identifier")
        if literal is not None:
            target = _safe_protocol_literal(literal) or "<non-protocol-string>"
            kind = "literal"
        else:
            target = identifier or "<expression>"
            kind = "identifier"
        item = {"method": method, "target_kind": kind, "target": target}
        if item not in http_calls:
            http_calls.append(item)

    named_calls = {
        name: [match.start() for match in re.finditer(rf"\b{re.escape(name)}\b", text)]
        for name in _NAMED_CALLS
    }
    named_calls = {name: positions[:80] for name, positions in named_calls.items() if positions}

    return {
        "protocol_literals": literals[:160],
        "protocol_identifiers": identifiers,
        "form_fields": form_fields,
        "mime_types": mime_types,
        "audio_extensions": extensions,
        "object_keys": object_keys,
        "http_calls": http_calls[:120],
        "named_calls": named_calls,
    }


def _read_member(path: Path, member: dict[str, Any]) -> bytes:
    with path.open("rb") as stream:
        stream.seek(member["absolute_start"])
        data = stream.read(member["size"])
    if len(data) != member["size"]:
        raise AsarFormatError(f"Unable to read complete ASAR member: {member['path']}")
    return data


def build_report(path: Path, offsets: Iterable[int], *, radius: int = 32768) -> dict[str, Any]:
    """Build a structural report for selected raw archive offsets."""
    offset_list = list(dict.fromkeys(int(offset) for offset in offsets))
    data_start, mappings = locate_members(path, offset_list)
    member_cache: dict[tuple[str, int], tuple[bytes, dict[str, Any]]] = {}
    targets: list[dict[str, Any]] = []

    for mapping in mappings:
        target_members: list[dict[str, Any]] = []
        for member in mapping["members"]:
            key = (member["path"], member["absolute_start"])
            if key not in member_cache:
                member_bytes = _read_member(path, member)
                member_text = member_bytes.decode("utf-8", errors="replace")
                member_cache[key] = (member_bytes, extract_structure(member_text))
            member_bytes, member_structure = member_cache[key]

            relative = member["relative_offset"]
            left = max(0, relative - radius)
            right = min(len(member_bytes), relative + radius)
            local_bytes = member_bytes[left:right]
            local_text = local_bytes.decode("utf-8", errors="replace")
            target_members.append(
                {
                    **member,
                    "member_sha256": hashlib.sha256(member_bytes).hexdigest(),
                    "member_structure": member_structure,
                    "local_window": {
                        "start": left,
                        "end": right,
                        "sha256_16": hashlib.sha256(local_bytes).hexdigest()[:16],
                        "structure": extract_structure(local_text),
                    },
                }
            )
        targets.append({"offset": mapping["offset"], "members": target_members})

    return {
        "format": "musicark-yandex-upload-target-report-v1",
        "source": "asar-targeted-static-scan",
        "input_name": path.name,
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "asar_data_start": data_start,
        "radius": radius,
        "targets": targets,
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
    print(f"Wrote targeted sanitized report: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Map selected Yandex Music app.asar offsets to members and extract safe protocol structure."
    )
    parser.add_argument("input", type=Path, help="Path to the official Yandex Music app.asar.")
    parser.add_argument(
        "--offset",
        type=int,
        action="append",
        required=True,
        help="Absolute byte offset from a previous binary report. Repeat for multiple targets.",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=32768,
        help="Bytes to inspect around each offset inside its ASAR member.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report instead of stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file does not exist: {args.input}")
    report = build_report(args.input, args.offset, radius=max(1024, args.radius))
    _write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
