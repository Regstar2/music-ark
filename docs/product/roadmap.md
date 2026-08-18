# MusicArk Roadmap

```text
v0.1   — Yandex Likes MVP                              complete
v0.2   — Persistent Library                            complete
v0.3   — Yandex Library / Playlists                    complete
v0.4   — Local Library                                 complete
v0.5.0 — Identity Matching                             complete
v0.5.1 — Variant / Altered Track Detection             complete
v0.6   — Missing Tracks / Coverage                     complete
v0.7   — Download + Local Playback                     complete
v0.8.0 — Controlled Sync                               complete
v0.8.1 — Rich Yandex download metadata/provenance      complete
v0.8.2 — Local Metadata Editor / Yandex Metadata       complete
v0.9.0 — UI, Account & Settings                        complete
v0.9.1 — Main Screen UI Polish                         complete
v0.9.2 — Local Library UI & Multi-Root Selection       complete
v0.9.3 — Matching UI Redesign                          complete
v0.9.4 — Coverage / Missing UI Polish                  complete
v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions    complete
v0.9.6 — Sync Page UI Polish                           complete
v0.9.7 — Large Library Performance                     current
v0.10.x — Yandex Upload                                next
```

## v0.8.0 — Controlled Sync

Yandex active collections are desired state; Local Library plus authoritative Coverage are actual state. Controlled Sync builds a read-only plan, previews safe downloads and blockers, validates staleness, requires explicit confirmation, rechecks each operation, and delegates acquisition to the production `DownloadService`.

Bulk acquisition remains `missing + wanted`. Unreviewed Missing, identity conflicts/not-analyzed state and unresolved Variant issues remain review work. `DIFFERENT_VERSION` never triggers automatic replacement. Local-only/outside-scope files are informational and are never deleted.

## v0.8.1 — Rich Yandex download metadata / provenance

The production Yandex download path writes available standard MP3 metadata and trusted MusicArk/Yandex provenance before atomic finalization. This keeps downloaded files useful after rescans and allows trusted provider identity recovery without weakening queue isolation or overwriting an existing user file on a filename collision.

## v0.8.2 — Local Metadata Editor / Yandex Metadata Import

v0.8.2 adds an explicit write boundary for existing user-owned MP3 files: structured/advanced ID3 editing, artwork and safe filename changes, Yandex search/Compare, selective Apply Metadata and explicit Apply + Bind. It also includes app-level ORIGINAL/CENSORED marks, reviewed-variant acceptance and Yandex artwork/playback.

Schema progression reaches `1.8.4` through forward-only migrations. Scan, Matching, Coverage and Sync remain non-mutating for existing user audio files; only an explicit Metadata Editor action may rewrite one.

## v0.9.0 — UI, Account & Settings

v0.9.0 adds the global desktop shell account control, Settings utility destination, persisted System/Light/Dark theme preference, persisted System/Russian/English locale preference, Flutter localization resources, offline Help and About/diagnostics. It does not add new music semantics.

The SQLite schema remains `1.8.4`; UI preferences are stored separately. The Yandex account contract is reused cache-first and logout remains the existing provider application boundary.

## v0.9.1 — Main Screen UI Polish

v0.9.1 removes the duplicate permanent Yandex navigation sidebar and makes the global MusicArk sidebar the only permanent application navigation. Liked tracks, Playlists and Albums use top-level Yandex workspace navigation, while collection contents use detail views with explicit back navigation.

The Yandex workspace becomes responsive for desktop resizing: search/sort/version-label controls reflow, wide track rows use table-like columns, compact rows retain the same actions, normal `available` status is hidden, and unavailable playback is disabled with explanatory presentation. ORIGINAL/CENSORED feature bridges remain explicit dependencies.

The release also centralizes small UI layout tokens, adds a theme-aware MusicArk mark, refines light/dark presentation and makes Now Playing responsive without adding new playback semantics. SQLite remains `1.8.4` and backend music behavior is unchanged.

## v0.9.2 — Local Library UI & Multi-Root Selection

v0.9.2 brings Local Library onto the same desktop presentation layer and adds a true multi-root view filter. The user can show all roots, one root, any subset, or no roots without mutating the configured library sources.

Filtering is executed in SQLite before count/search/sort/pagination through a typed root-ID query contract, so large libraries are not filtered from only the first Flutter page. Folder management remains independent from the display filter, and existing playback, metadata editing, content labels and read-only scan boundaries remain intact.

SQLite remains `1.8.4`.

## v0.9.3 — Matching UI Redesign

v0.9.3 turns Matching into a desktop comparison workspace with five summary metrics, counted filters, Search/Sort and side-by-side Yandex/local columns. Matching identity and Variant recording status stay separate, and narrow desktop layouts preserve comparison semantics through horizontal scrolling instead of changing the matching model.

## v0.9.4 — Coverage / Missing UI Polish

v0.9.4 makes Coverage track-first: compact local-coverage summary, counted status tabs, responsive filters, artwork from already persisted provider metadata and explicit Missing triage/download actions. Coverage semantics and the existing direct Download boundary remain unchanged.

## v0.9.5 — Downloads UI, Safe Deletion & Bulk Actions

v0.9.5 redesigns Downloads around compact task rows, search/status filters, lazy rendering and explicit bulk actions. Failed/needs-review task removal deletes only the task record, while retry/download-selected run only IDs produced by the current user action and do not wake unrelated queued work.

## v0.9.6 — Sync Page UI Polish

v0.9.6 presents Controlled Sync as one readable desktop workflow: responsive scope/folder controls, state summary, current/projected coverage, five primary metrics and a single counted/filterable plan list. Empty operation classes no longer consume large accordion sections, while narrow windows switch plan rows to a stacked presentation.

The underlying Controlled Sync contract does not change: filters are Flutter presentation state, Apply still requires confirmation and delegates only the existing safe operations. There is no local-file deletion, metadata rewrite, Yandex mutation, reverse sync or automatic Different-Version replacement. SQLite remains `1.8.4`.

## v0.9.7 — Large Library Performance

v0.9.7 removes repeated large-library work from normal navigation. Local Library activation becomes cache-first and keeps recursive scanning explicit; track materialization is limited to 250-row pages; incremental scan persistence writes actual deltas rather than touching every unchanged row; local artwork lookup is batched and caches negative cover results.

The Yandex workspace avoids copying the complete track collection in the default view, memoizes filtered/sorted results, debounces track search, uses fixed-extent list rows and bounds network-image decode sizes. SQLite remains `1.8.4` and no music-domain semantics change.

## Next — v0.10.x Yandex Upload

The next product slice is intended for explicit upload of user-owned local music into the user's Yandex Music collection. It is intentionally **not implemented in v0.9.7**. Its API, queue semantics, provider capabilities, matching rules and safety boundaries must be designed as a separate version after v0.9.7 acceptance.