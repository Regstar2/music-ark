# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.5.0 — Matching.**

MusicArk — Windows desktop-приложение для объединения библиотеки Яндекс Музыки и локальной музыкальной коллекции. v0.5 добавляет полностью локальное сопоставление provider tracks с индексированными аудиофайлами и сохраняет уверенность/ручные решения в общей SQLite БД.

## Что работает в v0.5

### Яндекс Музыка

- безопасный вход по Yandex Music OAuth token через системный credential store;
- cache-first сессия, «Мне нравится», плейлисты и offline cache;
- треки разных коллекций дедуплицируются по `(provider_id, external_id)` для matching.

### Local Library

- несколько локальных roots, native Windows folder picker и recursive scan;
- структурированные title, artists, album, album artist, duration и технические поля;
- incremental rescan, SQL search/sort/pagination;
- MusicArk не изменяет аудиофайлы.

### Сопоставление

```text
Yandex cache + Local Library
             ↓
      MatchingService
             ↓
      CandidateGenerator
             ↓
         MatchScorer
             ↓
       MatchDecision
             ↓
 matched / conflict / unmatched
             ↓
            SQLite
```

- новый раздел **«Сопоставление»** с summary и запуском matching;
- фильтры Все / Совпало / Требует проверки / Не найдено;
- search, sort и `limit`/`offset`;
- conflict detail с несколькими top candidates;
- manual accept (`match_method=manual`) и persistent reject;
- automatic rerun не перезаписывает manual match;
- удалённый local file инвалидирует старый link;
- `matcher_version=1` и fingerprints позволяют безопасно пересчитывать изменившиеся данные.

## Matching policy

Candidate generation использует индексированные `normalized_title`, `normalized_artists_text` и duration buckets. На один provider track detailed scoring получает максимум 40 кандидатов; полного Cartesian product `Yandex × Local` нет.

Normalization: Unicode NFKC, `casefold`, единые пробелы/пунктуация/dash variants. Multiple artists сравниваются как order-independent set. `Live`, `Remix`, `Acoustic`, `Instrumental`, `Remaster`, `Radio Edit` и другие смысловые маркеры не выбрасываются.

Scoring v1:

```text
title    0.50
artists  0.30
duration 0.15
album    0.05
```

Duration — только secondary signal. Filename — fallback. Строгий convention `yandex_<track_id>.<ext>` остаётся очень сильным exact-ID signal; случайное число в path не считается exact match.

Decision policy:

```text
AUTO MATCH >= 0.90 и margin до второго кандидата >= 0.04
CONFLICT   >= 0.70
UNMATCHED   < 0.70
```

Если два сильных кандидата близки по confidence, MusicArk выбирает `CONFLICT`, а не случайный auto-match. Главный quality gate — precision автоматических совпадений.

## Safety / privacy

v0.5 работает offline после заполнения Yandex cache и Local Library. Локальные metadata не отправляются в Yandex, OpenAI или сторонние matching/metadata APIs. Matching не переименовывает, не перемещает, не удаляет и не редактирует аудиофайлы и не изменяет Яндекс Музыку.

SQLite forward migration v0.5: `1.4.0`. Существующая `.musicark/musicark.db`, Yandex cache, local index и credentials не требуют удаления.

## Запуск для разработки на Windows

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements-yandex.txt
python -m unittest discover -s tests -v

$env:MUSICARK_PYTHON = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:MUSICARK_REPO_ROOT = (Get-Location).Path
Set-Location .\ui\musicark_ui
flutter pub get
flutter analyze
flutter test
flutter run -d windows
```

## Ручная Windows-проверка v0.5

Используйте Yandex Library и тестовую локальную коллекцию (например `C:\MusicArk-Test`). Проверить очевидные exact matches, сложные live/remix/acoustic cases, одинаковые title разных artists, конфликт с несколькими candidates, manual accept/reject, restart и rerun. Реальное качество matching нельзя считать подтверждённым до проверки на пользовательской библиотеке.

## Roadmap

```text
v0.1 — Yandex Likes MVP
v0.2 — Persistent Library
v0.3 — Yandex Library / Playlists
v0.4 — Local Library
v0.5 — Matching
v0.6 — Missing Tracks
v0.7 — Download
v0.8 — Sync
```

Download, Missing Tracks workflow, playback, metadata editing и sync не входят в v0.5.

Подробности: `docs/versions/v0.5.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`.
