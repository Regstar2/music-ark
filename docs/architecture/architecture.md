# MusicArk Architecture

## v0.3 runtime boundary

```text
Flutter desktop UI
        ↓ JSON subprocess bridge
musicark.mvp_bridge
        ↓
YandexLibraryService
   ┌────┴──────────────┐
   ↓                   ↓
CredentialStore   collection repositories
   ↓                   ↓
OS keyring          SQLite
                       ↑
YandexMusicProvider ───┘
        ↓
   yandex-music
```

Rules:

1. Flutter uses bridge DTOs only; it never imports provider or SQLite concepts.
2. `YandexLibraryService` orchestrates session, network phase, cache writes, and cache-first responses.
3. `YandexMusicProvider` is the only layer that sees third-party `yandex-music` objects.
4. Tokens stay in the OS credential store. SQLite stores account/library data, never the token.
5. Provider collections are universal: `liked` and `playlist:<external_id>` share the same snapshot/item tables.
6. Playlist item `position` is authoritative for original/Yandex order.
7. Full library refresh is metadata-oriented and does not eagerly request every playlist body.
8. Network failures must not erase the last successful local snapshot.

## SQLite collection model

`provider_collection_snapshots` stores collection identity, metadata, source order, activity, metadata refresh time, and content refresh time. `provider_collection_items` stores ordered item payloads.

Migration `1.2.0` is additive over v0.2 (`1.1.1`) and is idempotent. Existing `yandex_music/liked` rows and items are preserved. No user database deletion is required.

Playlist deletion after a successful index refresh removes that playlist snapshot and its membership so stale remote collections do not remain active indefinitely.

## Compatibility

`PersistentLibraryService`, legacy `YandexMusicProvider.list_playlists()`, and bridge aliases `refresh`/`cached` remain for v0.2/legacy tests. New desktop flows use `YandexLibraryService` and the v0.3 commands.

See [[providers]], [[storage]], and [[v0.3.0]].
