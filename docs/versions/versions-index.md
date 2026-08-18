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
| v0.8.1 | Yandex Metadata Preservation / Rich Download Metadata | complete |
| v0.8.2 | Local Metadata Editor / Yandex Metadata Import | complete |
| v0.9.0 | UI, Account & Settings | complete |
| v0.9.1 | Main Screen UI Polish | complete |
| v0.9.2 | Local Library UI & Multi-Root Selection | complete |
| v0.9.3 | Matching UI Redesign | current / Draft validation |
| v0.10.x | Yandex Upload | planned next; not implemented |

Version notes:

- `docs/versions/v0.1.0.md`
- `docs/versions/v0.2.0.md`
- `docs/versions/v0.3.0.md`
- `docs/versions/v0.4.0.md`
- `docs/versions/v0.5.0.md`
- `docs/versions/v0.5.1.md`
- `docs/versions/v0.6.0.md`
- `docs/versions/v0.7.0.md`
- `docs/versions/v0.8.0.md`
- `docs/versions/v0.8.1.md`
- `docs/versions/v0.8.2.md`
- `docs/versions/v0.9.0.md`
- `docs/versions/v0.9.1.md`
- `docs/versions/v0.9.2.md`
- `docs/versions/v0.9.3.md`

Current package version is `0.9.3`; current schema target remains `1.8.4`. v0.9.3 redesigns Matching as a side-by-side Yandex/Local comparison workspace with summary metrics, counted filters, compact confidence presentation and separate Matching/Variant status while preserving the existing bridge semantics, detail workflow and manual decisions.

v0.8.2 safety remains authoritative: ordinary Scan/Matching/Coverage/Sync do not rewrite existing user audio files, and Metadata Editor remains the explicit write boundary.

This index describes source state and does not by itself indicate that v0.9.3 has been published as a GitHub Release. Yandex Upload belongs to a separate future v0.10.x milestone.
