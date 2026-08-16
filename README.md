# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.8.0 — Controlled Sync.**

MusicArk — Windows desktop-приложение, связывающее cache-first библиотеку Яндекс Музыки с локальной музыкальной коллекцией. v0.5 устанавливает identity, v0.5.1 отдельно проверяет вариант записи, v0.6 выводит Coverage/Missing, v0.7 добавляет production Download + Local Playback, а v0.8 координирует эти готовые слои через безопасный dry-run Sync Plan.

## Основной цикл

```text
Yandex Library = desired state
        ↓
all / liked / Yandex Playlist
        ↓
Coverage + Matching + Variant + Local Library = actual state
        ↓
Controlled Sync Planner (read only)
        ↓
Preview / blockers / explicit confirmation
        ↓
execution-time revalidation
        ↓
DownloadService.enqueue() for current Missing + Wanted
        ↓
Downloads → normal v0.7 transfer/index/link/coverage
```

Sync не является двунаправленным filesystem mirror.

## Authoritative policy

Provider identity — `(provider_id, external_id)`. Одна identity в Liked и нескольких playlists считается один раз. Playlist duplicate occurrences не создают duplicate downloads.

```text
covered                      → no acquisition
missing + wanted             → ENQUEUE_DOWNLOAD
missing + unreviewed         → USER_DECISION_REQUIRED
missing + ignored            → summary / no download
needs_review                 → REVIEW_IDENTITY
not_analyzed                 → matching review blocker
covered + uncertain/altered/
different_version            → REVIEW_VARIANT
```

`DIFFERENT_VERSION` не превращается в Missing и не запускает replacement. Прямой v0.7 **Скачать** для одного Missing остаётся отдельным explicit user intent и не меняет консервативную bulk Sync policy.

## Controlled Sync safety

Каждый план — immutable snapshot с `planner_version`, scope, exact download target, input fingerprint, summary и операциями. Relevant изменение active Yandex membership, matching/local state, wanted/ignored triage или download target делает план `stale`. Playback state fingerprint не меняет.

Apply требует подтверждения и перед каждой actionable operation повторно проверяет:

```text
track still active/current?
coverage still missing?
action still wanted?
accepted local link still absent?
active user task already exists?
```

Затем вызывается production `DownloadService.enqueue()`. Sync **не вызывает `runQueue()`**, не запускает unrelated queued tasks и не содержит собственную HTTP download implementation.

Стандартный v0.8 Apply всегда даёт:

```text
deleted local files = 0
renamed/moved local files = 0
modified existing local files/tags = 0
Yandex mutations = 0
```

Local-only / Outside selected scope — только informational category.

## Existing layers remain independent

- **Yandex Library** — secure token via OS credential store, active cached Liked/playlists, offline cache.
- **Local Library** — multiple roots, incremental read-only indexing, structured metadata.
- **Identity Matching** — `MATCHED / CONFLICT / UNMATCHED` with manual precedence and fingerprints.
- **Variant** — `SAME / ALTERED / DIFFERENT_VERSION / UNCERTAIN / NOT_CHECKED`, independent from identity/Coverage.
- **Coverage** — derived `covered / missing / needs_review / not_analyzed` plus `wanted / ignored / unreviewed` triage.
- **Download** — v0.7 persistent user queue, exact target, secure provider acquisition, atomic `.part`, normal Local indexing, exact identity link, Coverage rebase.
- **Local Playback** — embedded player remains unchanged by v0.8.

## UI

```text
MusicArk
├── Яндекс Музыка
├── Локальная библиотека
├── Сопоставление
├── Недостающие
├── Загрузки
└── Синхронизация
```

«Синхронизация» показывает scope, target, Current/Projected coverage, download candidates, undecided Missing, identity/matching blockers, Variant issues, Local-only/Outside scope, stale/legacy state, confirmation, Apply result и историю Sync Plan.

## SQLite

Forward-only schema:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage actions
1.7.0 — Download queue/settings
1.8.0 — Controlled Sync plan snapshots/results
```

`1.7.0 → 1.8.0` расширяет существующие `sync_plans` / `sync_operations`, не создаёт parallel v2 tables и сохраняет legacy rows. Новый executor legacy upload/replace/metadata plans не выполняет.

Secrets (`Yandex token`, auth headers, cookies, temporary direct URLs) не хранятся в sync/download metadata.

## Запуск для разработки на Windows

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

## Roadmap

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
next   — TBD / stabilization
```

См. `docs/versions/v0.8.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md` и `docs/release/release-checklist.md`.
