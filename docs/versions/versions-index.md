# MusicArk Versions

| Version | Product slice | Status |
|---|---|---|
| v0.1.0 | Yandex Likes MVP | complete |
| v0.2.0 | Persistent Library | complete |
| v0.3.0 | Yandex Library / Playlists | complete |
| v0.4.0 | Local Library | complete |
| v0.5.0 | Identity Matching | complete |
| v0.5.1 | Variant / Altered Track Detection | complete |
| v0.6.0 | Missing Tracks / Library Coverage | current development |
| v0.7.0 | Download | planned |
| v0.8.0 | Sync | planned |

Version notes:

- `docs/versions/v0.1.0.md`
- `docs/versions/v0.2.0.md`
- `docs/versions/v0.3.0.md`
- `docs/versions/v0.4.0.md`
- `docs/versions/v0.5.0.md`
- `docs/versions/v0.5.1.md`
- `docs/versions/v0.6.0.md`

v0.5.0 and v0.5.1 intentionally remain separate layers: identity matching answers whether provider/local objects belong to the same track; variant verification answers whether that established identity is the same recording/version.

v0.6 adds a third derived analytical layer. Identity coverage (`covered/missing/needs_review/not_analyzed`), variant state, and user triage (`wanted/ignored/unreviewed`) remain independent. Future v0.7 Download consumes only technical `missing + wanted` candidates.

Standalone Windows packaging is infrastructure work and is not a substitute for the functional roadmap.
