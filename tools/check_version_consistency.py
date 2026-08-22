"""Fail when release-facing MusicArk version declarations drift."""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise SystemExit(f"Could not find {label} version declaration.")
    return match.group(1)


def main() -> int:
    canonical = _read("VERSION").strip()
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", canonical):
        raise SystemExit("VERSION must contain strict MAJOR.MINOR.PATCH SemVer.")

    values = {
        "pyproject.toml": _extract(r'^version\s*=\s*"([^"]+)"', _read("pyproject.toml"), "Python package"),
        "src/musicark/__init__.py": _extract(r'^__version__\s*=\s*"([^"]+)"', _read("src/musicark/__init__.py"), "backend"),
        "ui/musicark_ui/pubspec.yaml": _extract(r'^version:\s*([^+\s]+)', _read("ui/musicark_ui/pubspec.yaml"), "Flutter package"),
        "ui/musicark_ui/lib/app_info.dart": _extract(r"static const version = '([^']+)'", _read("ui/musicark_ui/lib/app_info.dart"), "Flutter AppInfo"),
    }
    backend = _extract(
        r"static const backendVersion = '([^']+)'",
        _read("ui/musicark_ui/lib/app_info.dart"),
        "Flutter backend",
    )
    values["ui/musicark_ui/lib/app_info.dart backend"] = backend

    mismatches = {name: value for name, value in values.items() if value != canonical}
    if mismatches:
        lines = [f"Canonical VERSION is {canonical}; mismatches:"]
        lines.extend(f"- {name}: {value}" for name, value in sorted(mismatches.items()))
        raise SystemExit("\n".join(lines))
    print(f"MusicArk version declarations are consistent: {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
