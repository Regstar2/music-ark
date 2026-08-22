# MusicArk Versions

| Version | Product slice | Status |
|---|---|---|
| v0.1.0 | Yandex Likes MVP | complete |
| v0.2.0 | Persistent Library | complete |
| v0.3.0 | Yandex Library / Playlists | complete |
| v0.4.0 | Local Library | complete |
| v0.5.0 | Identity Matching | complete |
| v0.5.1 | Variant / Altered Track Detection | complete |
| v0.6.0 | Missing Tracks / Library Coverage | complete |
| v0.7.0 | Download + Local Playback | complete |
| v0.8.0 | Controlled Sync | complete |
| v0.8.1 | Rich Yandex download metadata/provenance | complete |
| v0.8.2 | Local Metadata Editor / Yandex Metadata | complete |
| v0.9.x | Desktop UI improvement line | complete |
| v0.10.0 | Yandex Upload Feasibility | complete |
| v0.11.0 | Production Single-Track Yandex Upload | complete |
| v0.11.1 | Bulk Upload, Recovery Sync & Scope Context | complete |
| v0.12.0 | External Metadata & Resilient Network Access | complete |
| v0.13.0 | Multi-Format Audio & Safe Yandex Conversion | complete |
| v0.14.0 | Large Library Performance & Release Hardening | complete |
| v0.15.0 | Installer, Auto-Update, Feedback & Packaging | implementation |
| v1.0.0 | Release Freeze & Public Release | planned |

## Version notes

Historical version notes are stored under `docs/versions/`. The current release-hardening line uses:

- `docs/versions/v0.11.1.md`;
- `docs/versions/v0.12.0.md`;
- `docs/versions/v0.14.0.md`;
- `docs/versions/v0.15.0.md`.

A standalone `docs/versions/v0.13.0.md` was not present in the repository when v0.14 work began; v0.15 does not fabricate historical validation results for that merged version. The current source and regression suites remain authoritative for its multi-format/conversion behavior.

Current application/backend version target is `0.15.0`, Flutter is `0.15.0+1`, and the core SQLite schema target remains `1.9.0` because v0.15 introduces no music-database schema migration.

## Release line

The remaining pre-1.0 roadmap is intentionally frozen:

```text
v0.15.0 — Installer, Auto-Update, Feedback & Packaging
v1.0.0  — Release Freeze & Public Release
```

v0.15 introduces distribution code and packaging evidence only. No status in this index by itself implies that a tag, GitHub Release, public installer or stable update manifest has been published.
