"""Analyze a sanitized desktop upload trace into a stage-one ground-truth decision.

Input must be the secret-free report produced by ``yandex_upload_cdp_probe.py``.
The analyzer never accepts raw HAR/CDP input and never reconstructs credential or
signed URL values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


_PUBLIC_CLIENTS = {"YandexMusicDesktopApp", "YandexMusicWebNext"}
_AUTH_SOURCES = {"account-oauth", "custom-api-token", "session", "unknown", "none"}


def _unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("format") != "musicark-yandex-upload-cdp-runtime-report-v1":
        raise ValueError("Expected a sanitized MusicArk CDP runtime report.")
    safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}
    if any(value is not False for value in safety.values()):
        raise ValueError("Input report did not pass all sanitization safety gates.")

    events = report.get("events") if isinstance(report.get("events"), list) else []
    stage1_requests = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "request"
        and event.get("path") == "/loader/upload-url"
    ]
    stage1_responses = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "response"
        and event.get("path") == "/loader/upload-url"
    ]
    stage1_shapes = [
        event.get("bodyShape")
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "response-shape"
        and event.get("path") == "/loader/upload-url"
    ]
    runtime_events = [event for event in events if isinstance(event, dict) and event.get("event") == "runtime"]
    multipart_requests = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "request"
        and event.get("method") == "POST"
        and event.get("contentTypeKind") == "multipart-form-data"
    ]
    processing_requests = [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event") == "request"
        and ("ugc" in str(event.get("path") or "").lower() or "processing" in str(event.get("path") or "").lower())
    ]

    hosts = _unique(event.get("host") for event in stage1_requests)
    schemes = _unique(event.get("scheme") for event in stage1_requests)
    query_names = sorted({name for event in stage1_requests for name in (event.get("queryNames") or []) if isinstance(name, str)})
    header_names = sorted({name for event in stage1_requests for name in (event.get("headerNames") or []) if isinstance(name, str)})
    statuses = sorted({int(event["httpStatus"]) for event in stage1_responses if isinstance(event.get("httpStatus"), int)})

    auth_sources = _unique(
        event.get("authorizationSource")
        for event in runtime_events
        if event.get("authorizationSource") in _AUTH_SOURCES and event.get("authorizationSource") != "none"
    )
    public_clients = _unique(
        event.get("clientRemoteType")
        for event in runtime_events
        if event.get("clientRemoteType") in _PUBLIC_CLIENTS
    )
    custom_prefix_selected = any(event.get("customApiPrefixSelected") is True for event in runtime_events)
    custom_token_selected = any(event.get("customApiTokenPathSelected") is True for event in runtime_events)
    authorization_present = any(
        isinstance(event.get("authorization"), dict) and event["authorization"].get("present") is True
        for event in stage1_requests
    )

    if not stage1_requests:
        direct_decision = "needs-runtime-stage1-observation"
    elif len(hosts) != 1:
        direct_decision = "ambiguous-stage1-host"
    elif "account-oauth" in auth_sources and public_clients:
        direct_decision = "account-oauth-profile-candidate"
    elif "custom-api-token" in auth_sources or custom_token_selected:
        direct_decision = "private-desktop-credential-path-observed"
    elif "session" in auth_sources:
        direct_decision = "desktop-session-path-observed"
    else:
        direct_decision = "authorization-origin-not-proven"

    return {
        "format": "musicark-yandex-upload-ground-truth-decision-v1",
        "stage1": {
            "observed": bool(stage1_requests),
            "schemes": schemes,
            "hosts": hosts,
            "queryNames": query_names,
            "headerNames": header_names,
            "authorizationPresent": authorization_present,
            "httpStatuses": statuses,
            "responseShapes": stage1_shapes[:4],
        },
        "runtime": {
            "authorizationSources": auth_sources,
            "clientRemoteTypes": public_clients,
            "customApiPrefixSelected": custom_prefix_selected,
            "customApiTokenPathSelected": custom_token_selected,
        },
        "stage2": {
            "multipartPostObserved": bool(multipart_requests),
            "hosts": _unique(event.get("host") for event in multipart_requests),
            "paths": _unique(event.get("path") for event in multipart_requests),
        },
        "processing": {
            "requestObserved": bool(processing_requests),
            "paths": _unique(event.get("path") for event in processing_requests),
        },
        "directHttpDecision": direct_decision,
        "safety": {
            "credential_values_included": False,
            "header_values_included": False,
            "query_values_included": False,
            "signed_urls_included": False,
            "raw_trace_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a sanitized Yandex desktop upload CDP trace.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    decision = analyze(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote upload ground-truth decision: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
