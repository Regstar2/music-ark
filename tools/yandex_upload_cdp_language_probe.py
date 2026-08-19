"""Run the no-auth Chromium stage-one probe with renderer Accept-Language.

This diagnostic changes exactly one variable relative to
``yandex_upload_cdp_noauth_probe``: it explicitly adds the public
``Accept-Language`` header using the official Electron renderer's
``navigator.language`` value. Static research places ``accept-language`` in the
proven stage-one common request-header stack.

Authorization remains intentionally absent, browser credentials remain omitted,
and only stage one can be sent. The locale value itself is never returned or
persisted by this tool.
"""

from __future__ import annotations

import json
import sys

import yandex_upload_cdp_noauth_probe as noauth


_FORMAT = "musicark-yandex-upload-cdp-language-differential-v1"
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"


def _expression(*, endpoint: str, oauth_token: str) -> str:  # noqa: ARG001
    """Build the no-auth fetch with Accept-Language sourced from the renderer."""
    endpoint_literal = json.dumps(endpoint, ensure_ascii=False)
    client_literal = json.dumps(_DESKTOP_CLIENT_LABEL)
    return f"""
(async () => {{
  const endpoint = {endpoint_literal};
  const language = String(navigator.language || '').trim();
  if (!language) {{
    return {{networkCompleted: false, errorName: 'LanguageUnavailable'}};
  }}
  try {{
    const response = await fetch(endpoint, {{
      method: 'POST',
      headers: {{
        'Accept': 'application/json',
        'Accept-Language': language,
        'X-Yandex-Music-Client': {client_literal}
      }},
      credentials: 'omit',
      redirect: 'manual',
      cache: 'no-store'
    }});

    let responseShape = {{type: 'unavailable'}};
    let postTargetPresent = false;
    let pollResultPresent = false;
    let ugcTrackIdPresent = false;

    if (response.ok) {{
      try {{
        const payload = await response.json();
        if (payload && typeof payload === 'object' && !Array.isArray(payload)) {{
          const keys = Object.keys(payload).sort();
          const shapeKeys = {{}};
          for (const key of keys) {{
            const item = payload[key];
            shapeKeys[key] = {{
              type: Array.isArray(item) ? 'array' : (item === null ? 'null' : typeof item)
            }};
          }}
          responseShape = {{type: 'object', keys: shapeKeys}};
          postTargetPresent = typeof payload['post-target'] === 'string' && payload['post-target'].length > 0;
          pollResultPresent = typeof payload['poll-result'] === 'string' && payload['poll-result'].length > 0;
          ugcTrackIdPresent = typeof payload['ugc-track-id'] === 'string' && payload['ugc-track-id'].length > 0;
        }}
      }} catch (_) {{
        responseShape = {{type: 'unavailable'}};
      }}
    }}

    return {{
      networkCompleted: true,
      httpStatus: Number(response.status || 0),
      responseShape,
      postTargetPresent,
      pollResultPresent,
      ugcTrackIdPresent
    }};
  }} catch (error) {{
    return {{
      networkCompleted: false,
      errorName: error && error.name ? String(error.name) : 'Error'
    }};
  }}
}})()
""".strip()


def run(args):  # noqa: ANN001, ANN201
    original_expression = noauth._expression  # noqa: SLF001
    noauth._expression = _expression  # noqa: SLF001
    try:
        payload, code = noauth.run(args)
    finally:
        noauth._expression = original_expression  # noqa: SLF001

    payload["format"] = _FORMAT
    stage1 = payload.get("stage1") if isinstance(payload.get("stage1"), dict) else {}
    stage1["acceptLanguageSource"] = "electron-renderer-navigator.language"
    payload["stage1"] = stage1

    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    probe["differentialVariable"] = "accept-language-from-renderer"
    payload["probe"] = probe

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    safety["accept_language_value_included"] = False
    payload["safety"] = safety
    return payload, code


def main() -> int:
    parser = noauth.base.build_parser()
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
