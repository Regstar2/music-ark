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
| v0.8.1 | Yandex Metadata Preservation / Rich Download Metadata | current development |
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

v0.8.1 does not add a broader Sync executor. It hardens the existing v0.7 Download → Local indexing → exact identity path so MusicArk-created Yandex MP3 files carry durable standard metadata and trusted embedded provider provenance across rescans and a fresh Local Library index.
