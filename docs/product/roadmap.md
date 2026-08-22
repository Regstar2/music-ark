# MusicArk Roadmap

MusicArk is in feature freeze for the first public desktop release. The product scope through v1.0.0 is intentionally short and must not be expanded with new feature milestones during release hardening.

```text
v0.12.0 — External Metadata & Resilient Network Access       complete
v0.13.0 — Multi-Format Audio & Safe Yandex Conversion        complete
v0.14.0 — Large Library Performance & Release Hardening      complete
v0.15.0 — Installer, Auto-Update, Feedback & Packaging       implementation
v1.0.0  — Release Freeze & Public Release                    planned
```

## v0.12.0 — External Metadata & Resilient Network Access

Provider-neutral external metadata recovery, Yandex-first resolution, Chromaprint/AcoustID rescue, MusicBrainz/Cover Art Archive integration, proxy routing and Windows WARP management. External lookup remains an explicit operation and never runs merely because a Local Library row enters the viewport.

See `docs/versions/v0.12.0.md`.

## v0.13.0 — Multi-Format Audio & Safe Yandex Conversion

The local audio boundary was generalized beyond MP3 through the shared format capability/metadata adapter model. Upload conversion is explicit and source-safe: MusicArk may create a temporary Yandex-compatible derivative where required, but the source audio remains unchanged and temporary artifacts are cleaned up through the conversion/upload workflow.

## v0.14.0 — Large Library Performance & Release Hardening

Completed performance-hardening milestone. Local Library is cache-first, pagination and scan work are bounded, artwork/database hot paths are hardened, and deterministic 1k/10k/50k regression evidence is part of CI.

No new product capability was added in v0.14.0. See `docs/versions/v0.14.0.md`.

## v0.15.0 — Installer, Auto-Update, Feedback & Packaging

Current milestone. Scope is limited to distribution infrastructure:

- standalone Windows packaging without a separately installed Python runtime;
- per-user installer/uninstaller and portable package;
- one canonical release version contract;
- explicit fail-closed update discovery/download/apply flow with SHA-256 verification;
- GitHub bug/feature feedback entry points with privacy-safe diagnostics;
- package/runtime/update/feedback CI gates and release documentation.

The future public GitHub release/update location is a deployment-time channel, not a code-completeness blocker. No release/tag/stable manifest is published by this milestone itself.

See `docs/versions/v0.15.0.md`.

## v1.0.0 — Release Freeze & Public Release

Final release review, documentation/license/privacy checks, clean-install/upgrade validation, release artifacts and public GitHub release. Only release blockers are fixed here; feature development resumes after 1.0 on a separate roadmap.
