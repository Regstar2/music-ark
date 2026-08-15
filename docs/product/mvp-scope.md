# MVP / Product Scope

## Current supported slice: v0.6

1. Yandex Music cache-first library (Liked + playlists).
2. Read-only Local Library indexing.
3. v0.5 Identity Matching (`MATCHED/CONFLICT/UNMATCHED`).
4. v0.5.1 independent Variant Verification.
5. v0.6 Library Coverage / Missing Tracks with SQL scopes, filters, pagination and persistent wanted/ignored triage.

Out of scope for v0.6: actual missing-track download, download source selection, torrent/YouTube flow, automatic full-track Yandex acquisition, sync execution, local file mutation, Yandex library mutation, and treating v0.5.1 reference cache as Local Library.

Safety/privacy: Coverage is local analytics over existing cache/index/matching data and does not transmit the local library or missing list to third parties.
