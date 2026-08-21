# MusicArk Roadmap

MusicArk is in feature freeze for the first public desktop release. The product scope through v1.0.0 is intentionally short and must not be expanded with new feature milestones during release hardening.

```text
v0.12.0 — External Metadata & Resilient Network Access       complete
v0.13.0 — Multi-Format Audio & Safe Yandex Conversion        complete
v0.14.0 — Large Library Performance & Release Hardening      implementation
v0.15.0 — Installer, Auto-Update, Feedback & Packaging       planned
v1.0.0  — Release Freeze & Public Release                    planned
```

## v0.12.0 — External Metadata & Resilient Network Access

Provider-neutral external metadata recovery, Yandex-first resolution, Chromaprint/AcoustID rescue, MusicBrainz/Cover Art Archive integration, proxy routing and Windows WARP management. External lookup remains an explicit operation and never runs merely because a Local Library row enters the viewport.

See `docs/versions/v0.12.0.md`.

## v0.13.0 — Multi-Format Audio & Safe Yandex Conversion

The local audio boundary was generalized beyond MP3 through the shared format capability/metadata adapter model. Upload conversion is explicit and source-safe: MusicArk may create a temporary Yandex-compatible derivative where required, but the source audio remains unchanged and temporary artifacts are cleaned up through the conversion/upload workflow.

v0.14 performance work must preserve the v0.13 format registry rather than introducing MP3-only fast paths.

## v0.14.0 — Large Library Performance & Release Hardening

Current milestone. Scope is limited to measured performance waste, deterministic large-library regression coverage, cache-first Local Library behavior, scan/artwork/database hardening, large-list UI behavior and pre-release failure isolation.

No new product capability belongs in v0.14.0. See `docs/versions/v0.14.0.md`.

## v0.15.0 — Installer, Auto-Update, Feedback & Packaging

Distribution-only milestone. It will cover the production Windows installer/uninstaller, release packaging, update discovery/apply UX, GitHub feedback entry points and the documented ownership rules for optional managed dependencies such as WARP.

It must not reopen the product feature scope.

## v1.0.0 — Release Freeze & Public Release

Final release review, documentation/license/privacy checks, clean-install/upgrade validation, release artifacts and public GitHub release. Only release blockers are fixed here; feature development resumes after 1.0 on a separate roadmap.
