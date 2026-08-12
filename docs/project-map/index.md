# MusicArk Project Map

## Active desktop path

```text
ui/musicark_ui/
  lib/main.dart                 desktop Yandex Library UI
  lib/musicark_bridge.dart      subprocess bridge client

src/musicark/
  mvp_bridge.py                 JSON process boundary
  yandex_library.py             v0.3 application orchestration
  credentials.py                secure OS credential store
  providers/
    yandex_music_provider.py    Yandex API boundary
    yandex_mapper.py            provider DTO → MusicArk models
    models.py                   provider-neutral models
  storage/
    liked_cache.py              v0.2 Liked snapshot repository
    playlist_cache.py           v0.3 playlist index/content cache
    migrations.py               forward SQLite migrations
```

## Documentation entry points

- [[v0.3.0]] — current version contract
- `docs/architecture/architecture.md` — boundaries and storage model
- `docs/product/roadmap.md` — product sequence
- `docs/testing/manual-test-plan.md` — Windows/Yandex validation
- `docs/release/release-checklist.md` — release gate

Legacy modules remain in the repository where tests/older architecture still depend on them, but v0.3 Flutter must use the active path above rather than restoring the old multi-tab dashboard.
