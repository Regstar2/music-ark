# MusicArk Roadmap

## Product sequence

| Version | Focus | Status |
|---|---|---|
| v0.1 | Yandex Likes MVP | complete |
| v0.2 | Persistent Library | complete |
| v0.3 | Yandex Library / Playlists | implementation complete; real Windows/Yandex validation pending |
| v0.4 | Local Library | next |
| v0.5 | Matching | planned |
| v0.6 | Missing Tracks | planned |
| v0.7 | Download | planned |
| v0.8 | Sync | planned |

## v0.3 boundary

v0.3 turns the single Liked screen into a cache-first Yandex library with user playlists and ordered playlist snapshots. Playlist bodies are refreshed lazily; a full library refresh updates account, Likes, and playlist metadata.

## Not a current priority

Standalone Python packaging, installer work, local scanning, matching, downloading, playback, playlist editing/upload, and sync UI must not displace the product sequence above.

Next: [[v0.3.0]] → v0.4 Local Library.
