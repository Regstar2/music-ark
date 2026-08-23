"""Restricted frozen-runtime dispatcher used by packaged MusicArk builds.

The executable produced from this module intentionally implements only the
small subset of ``python`` invocation syntax used by MusicArk's Flutter process
bridges: ``--version`` and ``-m <approved musicark module> ...``. It is not a
general-purpose Python shell.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from collections.abc import Callable
from typing import TextIO

from musicark import __version__
from musicark import mvp_bridge, platform_bridge
from musicark.content_labels import bridge as content_labels_bridge
from musicark.download import bridge as download_bridge
from musicark.external_metadata import bridge as external_metadata_bridge
from musicark.matching import progress_bridge as matching_progress_bridge
from musicark.metadata import bridge as metadata_bridge
from musicark.recovery import bridge as recovery_bridge
from musicark.sync import bridge as sync_bridge
from musicark.upload import bridge as upload_bridge
from musicark.variant import acceptance_bridge
from musicark import feedback_bridge
from musicark.update import bridge as update_bridge

_ENTRY_POINTS: dict[str, Callable[[], int]] = {
    "musicark.mvp_bridge": mvp_bridge.main,
    "musicark.platform_bridge": platform_bridge.main,
    "musicark.content_labels.bridge": content_labels_bridge.main,
    "musicark.download.bridge": download_bridge.main,
    "musicark.external_metadata.bridge": external_metadata_bridge.main,
    "musicark.matching.progress_bridge": matching_progress_bridge.main,
    "musicark.metadata.bridge": metadata_bridge.main,
    "musicark.recovery.bridge": recovery_bridge.main,
    "musicark.sync.bridge": sync_bridge.main,
    "musicark.upload.bridge": upload_bridge.main,
    "musicark.variant.acceptance_bridge": acceptance_bridge.main,
    "musicark.feedback_bridge": feedback_bridge.main,
    "musicark.update.bridge": update_bridge.main,
}


def _configure_utf8_stdio(stdout: TextIO | None = None, stderr: TextIO | None = None) -> None:
    """Emit bridge JSON as UTF-8 even under non-UTF Windows code pages.

    Flutter decodes backend stdout/stderr as UTF-8. The frozen runtime therefore
    must not inherit a legacy console encoding such as cp1251, because a single
    Cyrillic error message can otherwise fail before the bridge returns JSON.
    """
    for stream in (stdout or sys.stdout, stderr or sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                # Some redirected or test streams cannot be reconfigured after
                # I/O. In that case the best available fallback is the
                # PYTHONIOENCODING environment set by the Flutter bridge.
                pass


def _packaged_data_root() -> Path:
    override = str(os.getenv("MUSICARK_DATA_ROOT", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve(strict=False)
    if os.name == "nt":
        local_app_data = str(os.getenv("LOCALAPPDATA", "") or "").strip()
        if local_app_data:
            return Path(local_app_data) / "MusicArk"
    home = Path.home()
    return home / ".musicark-data"


def _rewrite_packaged_arguments(args: list[str]) -> list[str]:
    """Keep mutable application state outside the installation directory.

    Older Flutter bridges still pass the packaged compatibility root as
    ``--base-dir``. A frozen runtime rewrites only that argument to the stable
    per-user data root before delegating to the existing backend entry point.
    """
    if not bool(getattr(sys, "frozen", False)):
        return args
    data_root = _packaged_data_root()
    data_root.mkdir(parents=True, exist_ok=True)
    os.environ["MUSICARK_DATA_ROOT"] = str(data_root)
    os.environ.pop("PYTHONPATH", None)
    result = list(args)
    try:
        index = result.index("--base-dir")
    except ValueError:
        return result
    if index + 1 >= len(result):
        return result
    result[index + 1] = str(data_root)
    return result


def main() -> int:
    _configure_utf8_stdio()
    args = sys.argv[1:]
    if args == ["--version"]:
        print(f"MusicArk runtime {__version__}")
        return 0
    if len(args) < 2 or args[0] != "-m":
        print(
            "MusicArk packaged runtime accepts only --version or -m <approved-module>.",
            file=sys.stderr,
        )
        return 2
    module = args[1]
    entry = _ENTRY_POINTS.get(module)
    if entry is None:
        print(f"Unsupported MusicArk runtime module: {module}", file=sys.stderr)
        return 2
    delegated = _rewrite_packaged_arguments(args[2:])
    # Make the delegated argparse parser see the same argv shape it would see
    # under ``python -m module ...``.
    sys.argv = [module, *delegated]
    return int(entry())


if __name__ == "__main__":
    raise SystemExit(main())
