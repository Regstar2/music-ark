# MusicArk — карта версий

## Актуальная product sequence

Эта карта синхронизирована с фактически реализованной desktop-линейкой. Старые файлы с ранними speculative названиями этапов сохранены как исторические материалы, но **не являются текущим roadmap**.

```text
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download + Local Playback
v0.8   — Controlled Sync
```

## Current

[[v0.8-sync-planner]] соответствует production `v0.8.0 — Controlled Sync`: Yandex Library задаёт desired state, Local Library/Coverage — actual state, а пользователь получает immutable preview, blockers, explicit confirmation, stale-plan protection и enqueue-only safe Apply через production `DownloadService`.

## После v0.8

Следующий крупный product scope **TBD / stabilization**. Файлы `v0.9-*`, `v0.10-*`, `v0.11-*`, `v1.*` в этой папке — ранние исторические идеи и не считаются обещанным порядком разработки.

## Ключевые актуальные модули

- [[local-archive]]
- [[matching-engine]]
- [[sync-planner]]
- [[sync-executor]]
- [[storage]]
- [[history-audit-log]]
- [[ui]]
- [[platform-bridge]]

Главное правило v0.8: Sync координирует существующие authoritative layers и не переизобретает Coverage, Matching, Download или Local indexing.
