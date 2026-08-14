# MVP / Product Scope

## Current supported product slice: v0.4

MusicArk v0.4 consists of two usable library sources:

1. **Yandex Music** — secure session, Liked tracks, playlists, cache-first persistence.
2. **Local Library** — user-selected Windows folders indexed into the same MusicArk SQLite database.

The local-library workflow is intentionally narrow:

```text
Add Folder → Scan → Read metadata → Persist index → Browse/Search/Sort
```

Supported local work includes persistent roots, incremental rescans, multiple artists as structured data, track details, error isolation, pagination-ready queries, and safe removal of index roots.

## Explicitly out of scope for v0.4

- Yandex ↔ local matching or fuzzy matching;
- missing-track detection;
- downloading or sync;
- playback/player;
- metadata editing;
- moving, renaming, deleting, or transcoding audio files;
- duplicate cleanup;
- album-art downloading;
- standalone packaging/installer.

## Safety requirement

The supported v0.4 Local Library is read-only with respect to user audio files. Destructive filesystem operations are not part of this product slice.
