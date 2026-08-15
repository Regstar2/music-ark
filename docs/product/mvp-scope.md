# MVP / Product Scope

## Current supported product slice: v0.6

MusicArk v0.6 has five usable analytical areas:

1. **Yandex Music** — secure session, Liked tracks, playlists, cache-first persistence.
2. **Local Library** — user-selected Windows folders indexed read-only into shared SQLite.
3. **Identity Matching** — v0.5 local analytical layer connecting unique Yandex track identities to plausible local files.
4. **Variant Verification** — v0.5.1 secondary recording/version analysis for accepted identities.
5. **Library Coverage / Missing Tracks** — v0.6 derived view separating Covered, Missing, Needs Review, and Not Analyzed plus persistent wanted/ignored triage.

The v0.6 workflow remains deliberately bounded:

```text
Yandex cache + Local index
        ↓
Run existing Matching
        ↓
MATCHED / CONFLICT / UNMATCHED
        +
optional Variant Verification
        ↓
Library Coverage
        ↓
covered / missing / needs_review / not_analyzed
        ↓
wanted / ignored / unreviewed
```

Supported coverage work includes global provider-identity deduplication, Liked/playlist scopes, playlist order, membership display, SQL summary/search/sort/filter/pagination, independent variant warnings, details/navigation into existing Matching, persistent per-track and bulk triage, stale-state handling, and offline operation after caches/index/matching are populated.

Critical semantic rules:

- current `UNMATCHED` only → `missing`;
- `CONFLICT` → `needs_review`;
- no/stale automatic result → `not_analyzed`;
- accepted current identity → `covered` regardless of SAME/ALTERED/DIFFERENT_VERSION/UNCERTAIN/NOT_CHECKED;
- reference cache is not Local Library coverage.

## Explicitly out of scope for v0.6

- actual Missing Tracks download/acquisition;
- download source selection, torrent/YouTube flow, automatic full-track Yandex acquisition;
- synchronization execution;
- playback/player;
- metadata editing;
- moving, renaming, deleting, transcoding, or deduplicating audio files;
- Yandex likes/dislikes/playlist edits/uploads;
- treating v0.5.1 reference cache as Local Library;
- standalone packaging/installer.

The existing bounded v0.5.1 exact-reference acquisition for an explicit single-track verification remains allowed and is not the v0.7 download workflow.

## Safety and privacy requirements

Matching, Variant Verification, and Coverage are read-only toward user audio and Yandex Music. Coverage runs from local cache/index data and must not send local library metadata, paths, matching state, or missing lists to external services.
