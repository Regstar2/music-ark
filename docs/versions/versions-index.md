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
| v0.8.0 | Controlled Sync | complete baseline |
| v0.8.1 | Yandex Metadata Preservation / Rich Download Metadata | complete baseline for v0.8.2 |
| v0.8.2 | Local Metadata Editor / Yandex Metadata Import | current development (`v8.2.0` branch) |
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

v0.8.2 adds an explicit transactional editor for existing local MP3 metadata/artwork/filename, structured Yandex Track search/compare/import, app-level ORIGINAL/CENSORED marks, and a separate user-confirmed exact identity action. Local Library scans automatically when its tab is activated; ordinary Scan/Matching/Coverage/Sync still never rewrite user audio files.
