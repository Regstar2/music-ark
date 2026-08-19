"""Run the Chromium stage-one upload probe without an Authorization header.

This diagnostic changes exactly one variable relative to the existing Chromium
OAuth failure-detail probe: Authorization is omitted. It still uses the same
localhost CDP path, endpoint/query construction, public desktop client label,
``credentials: 'omit'`` browser mode, and stage-one-only safety boundary.

The probe never reads or sends MusicArk's saved OAuth credential. It cannot send
audio or follow the dynamic stage-two target. Output remains sanitized: no query
values, response scalar values, cookies, request IDs, raw CDP messages, or header
values are emitted.
"""

from __future__ import annotations

import json
import sys

import yandex_upload_cdp_failure_detail_probe as detail
import yandex_upload_cdp_oauth_probe as base


_FORMAT = "musicark-yandex-upload-cdp-noauth-differential-v1"
_DESKTOP_CLIENT_LABEL = "YandexMusicDesktopApp"
_UNUSED_TOKEN_SENTINEL = "musicark-noauth-probe-unused-token"


def _expression(*, endpoint: str, oauth_token: str) -> str:  # noqa: ARG001
    """Build the same one-shot fetch while intentionally omitting Authorization."""
    endpoint_literal = json.dumps(endpoint, ensure_ascii=False)
    client_literal = json.dumps(_DESKTOP_CLIENT_LABEL)
    return f"""
(async () => {{
  const endpoint = {endpoint_literal};
  try {{
    const response = await fetch(endpoint, {{
      method: 'POST',
      headers: {{
        'Accept': 'application/json',
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
    original_expression = base._expression  # noqa: SLF001
    original_saved_token = base.live._saved_token  # noqa: SLF001
    base._expression = _expression  # noqa: SLF001
    base.live._saved_token = lambda _base_dir=None: _UNUSED_TOKEN_SENTINEL  # noqa: SLF001
    try:
        payload, code = detail.run(args)
    finally:
        base._expression = original_expression  # noqa: SLF001
        base.live._saved_token = original_saved_token  # noqa: SLF001

    payload["format"] = _FORMAT
    stage1 = payload.get("stage1") if isinstance(payload.get("stage1"), dict) else {}
    stage1["authorizationSource"] = "none"
    stage1["authorizationHeaderIntentionallyOmitted"] = True
    payload["stage1"] = stage1

    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    probe["differentialVariable"] = "authorization-header-omitted"
    payload["probe"] = probe

    safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
    safety.update(
        {
            "musicark_saved_oauth_read": False,
            "authorization_header_sent": False,
        }
    )
    payload["safety"] = safety
    return payload, code


def main() -> int:
    parser = base.build_parser()
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
