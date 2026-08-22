"""Small JSON process bridge for GitHub feedback entry points."""

from __future__ import annotations

import argparse
import json

from musicark.feedback import feedback_link, open_feedback


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="musicark-feedback-bridge")
    parser.add_argument("command", choices=("link", "open"))
    parser.add_argument("--kind", choices=("bug", "feature"), required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = feedback_link(args.kind).public_dict() if args.command == "link" else open_feedback(args.kind)
    except Exception as exc:  # noqa: BLE001 - keep process output sanitized.
        print(json.dumps({"error": {"code": "feedback_failed", "message": exc.__class__.__name__}}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
