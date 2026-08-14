# MVP / Product Scope

## Current supported product slice: v0.5

MusicArk v0.5 has three usable areas:

1. **Yandex Music** — secure session, Liked tracks, playlists, cache-first persistence.
2. **Local Library** — user-selected Windows folders indexed read-only into shared SQLite.
3. **Matching** — local analytical layer connecting unique Yandex track identities to plausible local files.

The v0.5 workflow is intentionally narrow:

```text
Yandex cache + Local index
        ↓
Run Matching
        ↓
bounded candidates
        ↓
score + ambiguity decision
        ↓
matched / conflict / unmatched
        ↓
manual accept/reject where needed
```

Supported matching work includes deterministic normalization, multiple artists, semantic title variants, duration/album secondary signals, strict exact-ID convention, indexed candidate lookup, score breakdown, persistent manual decisions, stale-link invalidation, pagination/search/sort, and conflict review.

## Explicitly out of scope for v0.5

- Missing Tracks product workflow;
- download/acquisition;
- synchronization;
- playback/player;
- metadata editing;
- moving, renaming, deleting, transcoding, or deduplicating audio files;
- Yandex likes/dislikes/playlist edits/uploads;
- torrent integration;
- standalone packaging/installer.

## Safety and privacy requirements

Matching is read-only toward both local audio and Yandex Music. It runs from local cache/index data and must not send local library metadata to external matching or metadata services.
