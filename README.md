# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.6.0 — Missing Tracks / Library Coverage.**

MusicArk — Windows desktop-приложение, которое связывает кешированную библиотеку Яндекс Музыки с read-only Local Library. v0.6 добавляет пользовательский workflow **«Недостающие треки»** поверх уже существующих v0.5 identity matching и v0.5.1 variant verification.

## Три независимых измерения

```text
Identity coverage: covered / missing / needs_review / not_analyzed
Variant:           same / altered / different_version / uncertain / not_checked
User action:       wanted / ignored / unreviewed
```

Они не смешиваются. `MISSING` означает только актуальный authoritative `UNMATCHED` без accepted local link. `CONFLICT`, stale state и отсутствие актуального matching result не считаются missing. `MATCHED + ALTERED/DIFFERENT_VERSION/UNCERTAIN/NOT_CHECKED` остаётся identity `COVERED`.

## v0.6 — Library Coverage

Новый `LibraryCoverageService` и SQL-backed `CoverageRepository` читают active Yandex collection membership, `matching_results`, `track_links`, Local Library и `track_variant_results`. Coverage не хранится отдельной копией: это derived view над authoritative tables.

Поддерживаются:

- summary: total / covered / missing / needs review / not analyzed;
- отдельный variant summary только для covered identity;
- `Local coverage` и отдельный `Matching analyzed` процент;
- scopes: вся кешированная Yandex-библиотека, «Мне нравится», конкретный playlist;
- глобальная дедупликация по `(provider_id, external_id)` и playlist order внутри playlist scope;
- поиск по title / artist / album / collection;
- SQL pagination/filter/sort;
- secondary filters для variant issues;
- details с переходом в существующий Matching workflow;
- persistent triage Missing-треков: **Нужен / Игнорировать / Не решено**;
- bulk triage без download-действий.

Future v0.7 contract:

```text
coverage_status = missing
AND user_action = wanted
```

## Reference audio v0.5.1

При explicit single-track variant verification текущая v0.5.1 реализация может bounded-способом получить exact reference в `.musicark/downloads/yandex`. Этот reference предназначен только для проверки версии записи.

**Reference cache не является Local Library.** Наличие `yandex_<id>.<ext>` не создаёт coverage и не создаёт `track_links`. Covered требует актуальный accepted v0.5 local identity match к обычному indexed Local Library file.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage user actions
```

v1.6 добавляет только `provider_track_actions(provider_id, external_id, action, created_at, updated_at)`. Отсутствие строки означает `unreviewed`. Coverage status не materialize-ится в отдельную таблицу.

Миграция не требует удаления `.musicark/musicark.db` и сохраняет Yandex cache, Local Library, matching/manual/conflict state и variant results.

## Safety / privacy

- Coverage работает локально поверх SQLite после заполнения cache/index;
- v0.6 не скачивает missing tracks;
- v0.6 не индексирует reference cache как Local Library;
- локальные файлы не удаляются, не переименовываются, не перемещаются и не редактируются;
- Yandex likes/playlists не мутируются;
- local metadata, paths, matching data и missing list не отправляются сторонним сервисам.

## Проверка на Windows

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

Подробности: `docs/versions/v0.6.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`.
