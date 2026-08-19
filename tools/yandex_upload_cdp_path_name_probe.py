"""Run the cached-UUID Chromium stage-one probe with filename-only path.

This diagnostic changes exactly one variable relative to the successful
``yandex_upload_cdp_playlist_uuid_probe`` setup used with ``--path-mode full``:
the recovered stage-one ``path`` query value is reduced from the absolute local
path to the selected file name.

All other safeguards remain inherited from the UUID probe: cached playlist UUID
is required, kind fallback is forbidden, Authorization is intentionally absent,
Accept-Language comes from the official Electron renderer, browser credentials
are omitted, only stage one is sent, and no query/header/credential/audio values
are returned.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import yandex_upload_cdp_playlist_uuid_probe as uuid_probe


_FORMAT = "musicark-yandex-upload-cdp-path-name-differential-v1"


def run(args: Any) -> tuple[dict[str, Any], int]:
    path_mode = str(args.path_mode or "").strip().lower()
    if path_mode != "name":
        raise uuid_probe.language.noauth.base.YandexUploadProtocolError(  # noqa: SLF001
            "Path-name differential requires --path-mode name."
        )

    payload, code = uuid_probe.run(args)
    payload["format"] = _FORMAT

    file_payload = payload.get("file") if isinstance(payload.get("file"), dict) else {}
    file_payload["stage1PathMode"] = "name"
    payload["file"] = file_payload

    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    probe["differentialVariable"] = "path-full-to-filename"
    payload["probe"] = probe

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    safety.update(
        {
            "path_value_included": False,
            "absolute_path_query_sent": False,
            "filename_only_path_query_sent": True,
        }
    )
    payload["safety"] = safety
    return payload, code


def main() -> int:
    parser = uuid_probe.language.noauth.base.build_parser()
    args = parser.parse_args()
    if args.launch_wait < 0 or args.launch_wait > 60:
        raise SystemExit("--launch-wait must be between 0 and 60 seconds")
    if args.timeout <= 0 or args.timeout > 120:
        raise SystemExit("--timeout must be between 0 and 120 seconds")
    try:
        payload, code = run(args)
    except Exception as exc:  # noqa: BLE001 - safe CLI boundary.
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
