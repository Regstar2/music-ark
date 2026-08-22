"""Generate a stable update manifest from a built Windows installer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _https(value: str, label: str) -> str:
    clean = value.strip()
    parsed = urlsplit(clean)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise SystemExit(f"{label} must be an absolute HTTPS URL.")
    return clean


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", choices=("stable", "beta"), default="stable")
    parser.add_argument("--asset-base-url", required=True)
    parser.add_argument("--release-notes-url", default="")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    installer = args.installer.resolve(strict=True)
    if installer.suffix.casefold() != ".exe":
        raise SystemExit("Installer must be an .exe file.")
    base = _https(args.asset_base_url.rstrip("/") + "/", "asset-base-url")
    installer_url = _https(urljoin(base, installer.name), "installer URL")
    release_notes = _https(args.release_notes_url, "release-notes-url") if args.release_notes_url.strip() else None
    payload = {
        "schemaVersion": 1,
        "channel": args.channel,
        "version": args.version,
        "publishedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "installer": {
            "url": installer_url,
            "sha256": _sha256(installer),
            "sizeBytes": installer.stat().st_size,
            "fileName": installer.name,
        },
        "releaseNotesUrl": release_notes,
    }
    output = args.output.resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
