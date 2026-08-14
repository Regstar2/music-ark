# MusicArk Project Map

## Active desktop path — v0.5

```text
ui/musicark_ui/
  lib/main.dart                 top-level Yandex / Local / Matching navigation
  lib/yandex_app.dart           Yandex Library UI
  lib/local_library_page.dart   Local Library UI
  lib/matching_page.dart        Matching summary/results/conflict review UI
  lib/musicark_bridge.dart      Yandex + Local subprocess bridge client
  lib/matching_bridge.dart      Matching subprocess bridge client

src/musicark/
  mvp_bridge.py                 JSON process boundary
  yandex_library.py             Yandex cache-first orchestration
  local_library/                local scan / metadata / service
  matching/
    input.py                    collection membership → unique provider identities
    indexer.py                  local normalized matching index refresh
    candidates.py               bounded SQL candidate generation
    scoring.py                  transparent candidate scoring
    service.py                  matching orchestration / decision / manual actions
    policy.py                   thresholds, weights, matcher version
    engine.py                   legacy compatibility facade
    models.py                   matching/canonical domain models
    normalize.py                deterministic matching normalization
  storage/
    matching_storage.py         matching persistence + result queries
    migrations.py               forward SQLite migrations (current 1.4.0)
```

## Documentation entry points

- `docs/versions/v0.5.0.md` — current version contract;
- `docs/architecture/architecture.md` — active boundaries and storage model;
- `docs/product/roadmap.md` — product sequence;
- `docs/testing/manual-test-plan.md` — Windows/real-library validation;
- `docs/release/release-checklist.md` — release gate.

Legacy modules remain where compatibility/tests depend on them, but the production v0.5 matcher is the layered pipeline above rather than the old Cartesian `MatchingEngine` implementation.
