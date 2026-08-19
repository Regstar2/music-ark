"""Run the complete offline Yandex upload ASAR research pipeline.

This orchestrator is intended for the Windows self-hosted GitHub Actions runner
and local research. It performs no network I/O, verifies the exact researched
official ``app.asar`` SHA-256, runs every current sanitized static probe, validates
all declared safety flags and writes only the resulting JSON reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import yandex_upload_prefix_provenance_probe as prefix_provenance
import yandex_upload_runtime_composition_probe as composition
import yandex_upload_runtime_config_probe as runtime_config
import yandex_upload_runtime_dataflow_probe as dataflow
import yandex_upload_runtime_profile_probe as runtime_profile
import yandex_upload_runtime_topology_probe as topology
import yandex_upload_stage1_role_probe as stage1_role


EXPECTED_ASAR_SHA256 = "8e7f4cec0776c39f194dee0a94086548d13f1465d46aa05d3e00a21624cbe80a"

_PROBES: tuple[tuple[str, Callable[[Path], dict[str, Any]]], ...] = (
    ("yandex-upload-runtime-profile-v15-ci.json", runtime_profile.build_report),
    ("yandex-upload-runtime-config-v16-ci.json", runtime_config.build_report),
    ("yandex-upload-runtime-dataflow-v17-ci.json", dataflow.build_report),
    ("yandex-upload-runtime-topology-v18-ci.json", topology.build_report),
    ("yandex-upload-runtime-composition-v19-ci.json", composition.build_report),
    ("yandex-upload-stage1-role-v20-ci.json", stage1_role.build_report),
    ("yandex-upload-prefix-provenance-v21-ci.json", prefix_provenance.build_report),
)

_REQUIRED_FALSE_SAFETY_FLAGS = {
    "network_requests_sent",
    "credential_values_included",
    "header_values_included",
    "query_values_included",
    "ordinary_string_values_included",
    "source_code_contexts_included",
    "raw_file_contents_included",
}
_OPTIONAL_FALSE_SAFETY_FLAGS = {"raw_identifiers_included", "raw_local_identifiers_included"}


def validate_report(report: dict[str, Any], *, expected_sha256: str) -> None:
    if report.get("input_sha256") != expected_sha256:
        raise ValueError("Runtime report input hash mismatch.")
    safety = report.get("safety")
    if not isinstance(safety, dict):
        raise ValueError("Runtime report has no safety contract.")
    for key in _REQUIRED_FALSE_SAFETY_FLAGS:
        if safety.get(key) is not False:
            raise ValueError(f"Runtime safety gate failed: {key}.")
    for key in _OPTIONAL_FALSE_SAFETY_FLAGS:
        if key in safety and safety.get(key) is not False:
            raise ValueError(f"Runtime safety gate failed: {key}.")


def run_pipeline(
    asar: Path,
    output_dir: Path,
    *,
    expected_sha256: str = EXPECTED_ASAR_SHA256,
) -> dict[str, Any]:
    if not asar.is_file():
        raise ValueError("Official Yandex Music app.asar is not available.")
    actual_sha256 = hashlib.sha256(asar.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("Yandex Music app.asar SHA-256 does not match the researched desktop build.")

    output_dir.mkdir(parents=True, exist_ok=True)
    completed: list[dict[str, str]] = []
    for filename, builder in _PROBES:
        report = builder(asar)
        validate_report(report, expected_sha256=expected_sha256)
        output = output_dir / filename
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        completed.append({"file": filename, "format": str(report.get("format") or "unknown")})

    manifest = {
        "format": "musicark-yandex-upload-offline-research-manifest-v1",
        "input_sha256": expected_sha256,
        "reports": completed,
        "networkMutation": False,
        "safetyValidated": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all sanitized Yandex upload ASAR research probes.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_ASAR_SHA256)
    args = parser.parse_args()
    try:
        manifest = run_pipeline(args.input, args.output_dir, expected_sha256=args.expected_sha256.lower())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Validated {len(manifest['reports'])} sanitized offline upload research reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
