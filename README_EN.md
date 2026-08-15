# MusicArk

[Русская версия](README.md)

**Current version: 0.6.0 — Missing Tracks / Library Coverage.**

MusicArk is a Windows desktop application that connects a cached Yandex Music library with a read-only Local Library. v0.6 adds the **Missing Tracks** workflow above the existing v0.5 identity matcher and v0.5.1 recording-variant verification.

## Three independent dimensions

```text
Identity coverage: covered / missing / needs_review / not_analyzed
Variant:           same / altered / different_version / uncertain / not_checked
User action:       wanted / ignored / unreviewed
```

`MISSING` means only a current authoritative `UNMATCHED` result with no accepted current local link. `CONFLICT`, stale state, and the absence of a current matching result are not missing. Any current accepted identity remains `COVERED` even when its variant is `ALTERED`, `DIFFERENT_VERSION`, `UNCERTAIN`, or `NOT_CHECKED`.

## v0.6 Library Coverage

`LibraryCoverageService` uses a SQL-backed `CoverageRepository` over active Yandex collection membership, `matching_results`, `track_links`, Local Library, and `track_variant_results`. Coverage is a derived view; it is not copied into a `missing_tracks` table.

The desktop page provides summary percentages, all/Liked/playlist scopes, unique provider identity deduplication, playlist-order preservation, search/sort/pagination, independent variant issue filters, matching details/navigation, and persistent Missing-track triage (`wanted`, `ignored`, or no row = `unreviewed`). Bulk triage is supported. v0.6 contains no download action.

Future v0.7 input is deliberately simple:

```text
coverage_status = missing
AND user_action = wanted
```

## v0.5.1 reference audio boundary

The current tested v0.5.1 implementation may acquire one exact reference during an explicit single-track variant verification and cache it under `.musicark/downloads/yandex`. This bounded verification mechanism is not the Missing Tracks download workflow.

A cached reference is **not Local Library coverage** and is never automatically promoted into Local Library or `track_links`. Coverage requires an accepted v0.5 identity link to a normal indexed local file.

## SQLite

```text
1.3.0 Local Library
1.4.0 Identity Matching
1.5.0 Variant Detection
1.6.0 Coverage user actions
```

v1.6 adds only `provider_track_actions(provider_id, external_id, action, created_at, updated_at)`. Existing Yandex cache, Local Library, identity/manual/conflict data, and variant results are preserved by an automatic forward migration.

## Safety / privacy

Coverage operates locally after the Yandex cache and Local Library index are populated. v0.6 does not download missing tracks, mutate Yandex, mutate local music files, or send local paths/matching/missing-list data to third parties.

## Windows validation

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -p "test_*.py" -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```
