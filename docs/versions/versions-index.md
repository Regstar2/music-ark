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
| v0.9.3 | Matching UI Redesign | complete |
| v0.9.4 | Coverage / Missing UI Polish | complete |
| v0.9.5 | Downloads UI, Safe Deletion & Bulk Actions | complete |
| v0.9.6 | Sync Page UI Polish | complete |
| v0.9.7 | Settings, Help & About UI Polish | current / Draft validation |
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
- `docs/versions/v0.9.4.md`
- `docs/versions/v0.9.5.md`
- `docs/versions/v0.9.6.md`
- `docs/versions/v0.9.7.md`

Current package version is `0.9.7`; current schema target remains `1.8.4`. v0.9.7 redesigns Settings, Help and About as constrained responsive desktop utility pages and expands the offline RU/EN Help into eleven workflow topics.

The utility-page release does not change music-domain truth or mutation boundaries. Settings preferences remain UI-only state; Help describes the existing behavior; About diagnostics remain credential- and library-content-free.

v0.9.6 Controlled Sync boundaries remain authoritative: existing local audio is not deleted/moved/renamed/retagged, Yandex collections are not mutated, Apply still requires confirmation, and `DIFFERENT_VERSION` never triggers automatic replacement.

v0.9.5 safe task deletion remains unchanged: removing a failed/needs-review download task removes only the task record and does not delete the final audio file, Local Library, Matching, Coverage, Wanted state or audit history.

v0.8.2 safety remains authoritative: ordinary Scan/Matching/Coverage/Sync do not rewrite existing user audio files, and Metadata Editor remains the explicit write boundary.

This index describes source state and does not by itself indicate that v0.9.7 has been published as a GitHub Release. Yandex Upload belongs to a separate future v0.10.x milestone.
