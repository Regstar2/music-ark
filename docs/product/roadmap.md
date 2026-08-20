# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                              complete
v0.2   — Persistent Library                            complete
v0.3   — Yandex Library / Playlists                    complete
v0.4   — Local Library                                 complete
v0.5.0 — Identity Matching                             complete
v0.5.1 — Variant / Altered Track Detection             complete
v0.6   — Missing Tracks / Coverage                     complete
v0.7   — Download + Local Playback                     complete
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata       complete
v0.9.x — Desktop UI improvement line                   complete
v0.10.0 — Yandex Upload Feasibility                    complete
v0.11.0 — Production Single-Track Yandex Upload        complete
v0.11.1 — Bulk Upload, Recovery Sync & Scope Context   complete
v0.12.0 — External Metadata & Resilient Network Access implementation
next    — Format support/conversion and upload polish   planned
later   — Auto-update, installer/release, mobile        planned
```

## Current architecture

MusicArk treats Yandex Music as the first production music provider, not as the global domain model. Local Library, Identity Matching, Variant analysis, Coverage, Download, Controlled Sync, metadata editing and upload/recovery remain explicit layers with separate mutation boundaries.

## v0.8.0 — Controlled Sync

Yandex active collections are desired state; Local Library plus authoritative Coverage are actual state. Controlled Sync creates a read-only plan, validates staleness, requires explicit confirmation and delegates only supported operations. It does not delete local-only files or silently replace different versions.

## v0.8.1 — Rich Yandex metadata/provenance

Authorized Yandex downloads write available standard MP3 metadata and trusted MusicArk/Yandex provenance before atomic finalization. This allows exact provider identity recovery without weakening queue isolation or overwriting a user file on filename collision.

## v0.8.2 — Local Metadata Editor

The Metadata Editor is the explicit transactional write boundary for existing user-owned audio. It supports structured/advanced ID3 editing, artwork, safe rename, Yandex search/Compare, selective Apply and explicit Yandex Apply + Bind. Scan, Matching, Coverage and Sync do not rewrite existing user audio files.

## v0.9.x — Desktop UI line

The v0.9.x line introduced account/settings shell, localization/theme support, responsive Yandex/Local/Matching/Coverage/Downloads/Sync pages, safe deletion/bulk actions, Help and diagnostics without changing the domain safety boundaries.

## v0.10.0 — Upload feasibility

The initial upload milestone researched Yandex own-track upload and kept production capability fail-closed until a reproducible account-owned protocol could be demonstrated.

## v0.11.0 — Production Single-Track Yandex Upload

v0.11.0 promotes the proven direct-Python upload protocol into an explicit one-track Local Library action. It keeps upload credentials, signed targets and uncertain-delivery handling behind a narrow provider transport boundary and never blindly retries an ambiguous Stage 2 delivery.

## v0.11.1 — Bulk Upload & Recovery Sync

v0.11.1 preserves the v0.11.0 single-track service as the only one-file upload primitive and adds sequential batch upload, persistent upload mappings, managed recovery playlists, unavailable-provider history and controlled Sync upload operations for deterministic recovery cases. Playlist creation remains fail-closed until separately live-proven.

## v0.12.0 — External Metadata & Resilient Network Access

v0.12.0 adds a provider-neutral external metadata layer for recovering/enriching one local file without weakening the Metadata Editor write boundary. The main sequence is cache-first and evidence-driven: trusted identity → Chromaprint/AcoustID → MusicBrainz Recording/Release → Cover Art Archive and optional fallback sources. Multiple releases remain separate candidates and no external result silently binds a Yandex identity or changes ORIGINAL/CENSORED state.

The same milestone introduces an external-network transport with Direct, Custom HTTP(S)/SOCKS5 Proxy, Cloudflare WARP local proxy and Auto modes. Auto falls back only for transport-level failures and caches working routes briefly so an inaccessible host does not impose the same timeout for every track. Yandex upload transport is deliberately excluded from this routing layer.

Windows-specific Cloudflare integration stays below the platform-neutral network boundary. MusicArk can detect/control an official WARP installation and has a fail-closed verified installation path; ownership is persisted only when MusicArk performed the successful install. A future uninstaller must preserve pre-existing WARP.

See `docs/versions/v0.12.0.md` and `docs/architecture/external-metadata-sources.md`.

## Next

The previous upload-queue work is largely covered by v0.11.1's sequential batch/recovery primitives. The next milestones should focus on broader audio-format read/write support, explicit conversion where Yandex requires it, performance on very large libraries, then auto-update and production installer/release work. Installer work must integrate the documented WARP ownership rules rather than treating every detected WARP installation as MusicArk-owned.
