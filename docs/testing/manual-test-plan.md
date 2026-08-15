# Manual Test Plan — MusicArk v0.6.0

Do not delete `.musicark\musicark.db`, credentials, music files, matching/manual state, or variant results.

## Migration

1. Start from a real v0.5.1 DB.
2. Launch v0.6 and confirm automatic schema `1.5.0 → 1.6.0`.
3. Confirm Yandex cache/session, Local Library roots/files, matching results, manual accept/reject/conflicts and variant results are preserved.

## Coverage truth

1. Load Yandex Library, scan Local Library and run Matching.
2. Open **Недостающие**; default filter must be Missing.
3. Confirm current `UNMATCHED → Missing`.
4. Confirm `CONFLICT → Needs Review`, never Missing.
5. Confirm no/currently-stale automatic result → Not Analyzed, never Missing.
6. Confirm current accepted identity → Covered.
7. Confirm `MATCHED + DIFFERENT_VERSION/ALTERED/UNCERTAIN/NOT_CHECKED` stays Covered with a separate variant warning.
8. Compare summary counts with Matching source state.

## Scopes / identity

- All, Liked and several playlists return correct counts.
- One provider track occurring in Liked + multiple playlists counts once globally.
- Playlist scope keeps Yandex order.
- Row/detail shows all known collection memberships.
- Remove a track from all active Yandex collections and refresh: it disappears from active coverage.

## Triage

- Mark several Missing rows wanted and ignored; reset one.
- Restart: decisions persist.
- Rerun matching so one wanted Missing becomes Matched: it becomes Covered and no longer qualifies as active Missing+wanted.
- Bulk wanted/ignored/reset works and there is no Download action.

## Stale state

- After a Local Library rescan changes the matching fingerprint, an old automatic UNMATCHED must become Not Analyzed until Matching reruns.
- A v0.5 manual match that becomes stale must become Needs Review according to existing manual-state rules.

## Reference regression

Use/obtain one v0.5.1 strict reference file in `.musicark\downloads\yandex` for an explicit variant check. With no accepted indexed Local Library link and current matching `UNMATCHED`, Coverage must remain `MISSING`. The reference must not be inserted into Local Library or `track_links`.

## Offline / safety

After cache/scan/matching are populated, disconnect the network and verify Coverage/search/filter/triage still work. Confirm v0.6 does not modify local audio, Yandex, credentials, or reference files.

## Automated commands

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter analyze
flutter test
```
