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
| v0.8.2 | Local Metadata Editor / Yandex Metadata Import | current code baseline / mainline candidate |
| next | stabilization / TBD | TBD |

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

Current package version is `0.8.2`; current schema target is `1.8.4`. v0.8.2 adds an explicit transactional editor for existing local MP3 metadata/artwork/filename, structured Yandex Track search/compare/import, app-level ORIGINAL/CENSORED marks, reviewed-variant acceptance, Yandex artwork/playback and the narrow-window safeguard. Ordinary Scan/Matching/Coverage/Sync still do not rewrite existing user audio files.

This index describes source state and does not by itself indicate that v0.8.2 has been published as a GitHub Release.
