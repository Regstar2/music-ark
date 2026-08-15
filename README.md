# MusicArk

[English version](README_EN.md)

**Текущая версия: 0.6.0 — Missing Tracks / Library Coverage.**

MusicArk — Windows desktop-приложение для объединения библиотеки Яндекс Музыки и локальной музыкальной коллекции. v0.5.0 сопоставляет provider tracks с локальными файлами, v0.5.1 отдельно проверяет версию записи, а v0.6 добавляет **Library Coverage / Missing Tracks** поверх этих authoritative результатов.

## Что работает

### Яндекс Музыка

- безопасный вход по Yandex Music OAuth token через системный credential store;
- cache-first сессия, «Мне нравится», плейлисты и offline cache;
- треки разных коллекций дедуплицируются по `(provider_id, external_id)` для matching и coverage.

### Local Library

- несколько локальных roots, native Windows folder picker и recursive scan;
- структурированные title, artists, album, album artist, duration и технические поля;
- incremental rescan, SQL search/sort/pagination;
- MusicArk не изменяет аудиофайлы.

### v0.5.0 — Identity Matching

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
 MATCHED / CONFLICT / UNMATCHED
```

- bounded candidate lookup вместо полного `Yandex × Local` Cartesian product;
- прозрачный score breakdown;
- conflict detail с несколькими кандидатами;
- manual accept и persistent reject;
- automatic rerun не перезаписывает manual match;
- удалённый local file инвалидирует старый link;
- matcher/provider/local fingerprints позволяют безопасные incremental reruns.

Identity policy не изменён v0.5.1/v0.6:

```text
AUTO MATCH >= 0.90 и margin до второго кандидата >= 0.04
CONFLICT   >= 0.70
UNMATCHED   < 0.70
```

Главный quality gate identity matching — precision автоматических совпадений.

### v0.5.1 — Variant Verification

После установленной identity-связи MusicArk задаёт второй вопрос:

```text
MATCHED / manual accepted link
             ↓
    VariantDetectionService
             ↓
       metadata evidence
             ↓
    exact reference audio?
             ↓
      decoded comparison
             ↓
SAME / ALTERED / DIFFERENT_VERSION /
UNCERTAIN / NOT_CHECKED
```

Identity confidence и variant/audio result **не объединяются в один confidence**.

Metadata-level анализ распознаёт смысловые маркеры, включая:

`Live`, `Remix`, `Mix`, `Acoustic`, `Instrumental`, `Remaster(ed)`, `Radio Edit`, `Radio Version`, `Edit`, `Extended`, `Demo`, `Clean`, `Explicit`, `Censored`, `Uncensored`.

Yandex `content_warning → explicit` используется только как evidence. `explicit=true/false` сам по себе не доказывает censored/uncensored версию.

### v0.6 — Library Coverage / Missing Tracks

v0.6 не строит второй matcher. `LibraryCoverageService` и SQL-backed `CoverageRepository` читают active Yandex membership, `matching_results`, `track_links`, Local Library и `track_variant_results` и выводят четыре primary состояния:

```text
covered       — актуальный accepted local identity match
missing       — актуальный authoritative UNMATCHED без accepted local link
needs_review  — CONFLICT / stale manual / invalid accepted link
not_analyzed  — нет актуального matching result или automatic result stale
```

Три измерения независимы:

```text
Identity coverage: covered / missing / needs_review / not_analyzed
Variant:           same / altered / different_version / uncertain / not_checked
User action:       wanted / ignored / unreviewed
```

`MATCHED + ALTERED/DIFFERENT_VERSION/UNCERTAIN/NOT_CHECKED` остаётся `covered`. `CONFLICT` и `not_analyzed` никогда не подменяются `missing`.

Раздел **«Недостающие»** открывается на Missing по умолчанию и поддерживает summary, scopes «Вся библиотека / Мне нравится / playlist», membership, playlist order, search, sort, pagination, variant filters, details, переход в существующее «Сопоставление» и persistent triage **Нужен / Игнорировать / Не решено**. Coverage status не materialize-ится в отдельную таблицу.

Future v0.7 contract:

```text
coverage_status = missing
AND user_action = wanted
```

## Reference audio

Для глубокого v0.5.1 audio verification используется только строгий convention:

```text
.musicark/downloads/yandex/yandex_<track_id>.<ext>
.musicark/downloads/yandex/yandex-<track_id>.<ext>
```

Пример:

```text
.musicark/downloads/yandex/yandex_69046542.mp3
```

Случайное число в path не считается Yandex ID. Актуальная tested v0.5.1 реализация при **явном single-track `variant_run`** может bounded-способом получить один exact reference, если его нет. Batch не скачивает библиотеку целиком.

**Reference cache не является Local Library.** Полученный reference не добавляется в `local_audio_files`, не создаёт `track_links` и сам по себе никогда не делает track `covered`.

## Audio verification

v0.5.1 сравнивает decoded audio, а не MP3/FLAC bytes. SHA-256 разных encoding не используется как доказательство одинаковой записи.

Pipeline:

```text
FfmpegAudioDecoder
    ↓
mono / signed-16 PCM / 11025 Hz через pipe
    ↓
bounded alignment ±15 s
    ↓
2.0 s windows / 0.75 s hop
    ↓
energy + spectral + waveform evidence
    ↓
merged altered regions
    ↓
VariantClassifier
```

Соседние bad windows объединяются в регионы вида `01:12–01:14`, а одиночные слабые outliers подавляются.

### ffmpeg

ffmpeg — **optional capability**, а не hard dependency MusicArk. Проверить наличие:

```powershell
ffmpeg -version
```

Если ffmpeg отсутствует:

- приложение запускается;
- Yandex/Local Library работают;
- v0.5 identity matching и v0.6 Coverage работают;
- metadata variant evidence остаётся доступным;
- UI явно показывает недоступность audio verification;
- техническая ошибка не превращается в `DIFFERENT VERSION`.

## Classification policy

- `SAME` — metadata совместимы, decoded audio стабильно совпадает, существенных altered regions нет;
- `ALTERED` — большая часть записи совпадает, но есть небольшие устойчивые локальные divergence regions;
- `DIFFERENT VERSION` — сильный semantic marker mismatch, существенная duration-разница или распределённое audio divergence;
- `UNCERTAIN` — signals конфликтуют или находятся около границ;
- `NOT CHECKED` — audio verification не запускался/нет reference/decoder недоступен.

Если provider помечен explicit, duration близка, большая часть audio совпадает и есть локальные изменения, MusicArk может добавить reason `possible_clean_or_censored_variant`. Это **не гарантированное определение цензуры или текста песни**.

## Cache / performance

Audio verification выполняется только после v0.5 matching — не для всех сочетаний Yandex и Local Library.

Результат кешируется по независимым fingerprints:

- provider metadata, relevant для variant analysis;
- local path + size + `mtime_ns`;
- reference path + size + `mtime_ns`;
- `ANALYZER_VERSION`.

Неизменившаяся успешная пара не декодируется повторно. Local/reference/provider change инвалидирует результат при следующей verification. Batch `Проверить все доступные` ограничен `MATCHED` парами с exact reference и не передаёт PCM через Flutter bridge.

Coverage summary/list/search/filter/sort/pagination выполняются SQL-side и не materialize-ят всю provider library во Flutter. Global coverage дедуплицирует `(provider_id, external_id)` между Liked/playlists.

## UI

В разделе **Сопоставление** identity и variant показываются отдельно:

```text
MATCHED 98%
Версия: SAME
```

или:

```text
MATCHED 99%
Версия: ALTERED
```

Detail dialog показывает Identity и Variant отдельно. Раздел **«Недостающие»** добавляет coverage summary и triage, не дублируя matching UI.

## SQLite

Forward-only schema history:

```text
1.3.0 — Local Library
1.4.0 — Identity Matching
1.5.0 — Variant Detection
1.6.0 — Coverage user actions
```

`track_variant_results` хранит status/evidence/similarity/regions/fingerprints, но не PCM/audio blobs. v1.6 добавляет только `provider_track_actions(provider_id, external_id, action, created_at, updated_at)`; отсутствие row означает `unreviewed`.

Существующая `.musicark/musicark.db`, Yandex cache, Local Library, v0.5 matches/manual decisions/conflicts и v0.5.1 variant results сохраняются forward migration и не требуют удаления.

## Safety / privacy

- matching, variant analysis и coverage работают локально после заполнения cache;
- нет внешних matching/metadata/fingerprint APIs;
- v0.6 не скачивает missing tracks;
- bounded v0.5.1 reference acquisition не считается Download workflow;
- локальные аудиофайлы не переименовываются, не перемещаются, не удаляются и не редактируются;
- Яндекс Музыка не модифицируется;
- PCM не отправляется через Flutter↔Python bridge и не хранится в БД.

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

## Ручная Windows-проверка v0.6

Проверить на реальной библиотеке summary против Matching, четыре coverage-состояния, Liked/playlist scopes и order, `MATCHED + DIFFERENT_VERSION`, wanted/ignored/bulk triage с restart, rerun Matching, offline Coverage и regression `strict reference exists + no accepted Local Library link → MISSING`.

## Roadmap

```text
v0.1   — Yandex Likes MVP
v0.2   — Persistent Library
v0.3   — Yandex Library / Playlists
v0.4   — Local Library
v0.5.0 — Identity Matching
v0.5.1 — Variant / Altered Track Detection
v0.6   — Missing Tracks / Coverage
v0.7   — Download
v0.8   — Sync
```

Download, source selection, playback, metadata mutation и sync не входят в v0.6.

Подробности: `docs/versions/v0.6.0.md`, `docs/architecture/architecture.md`, `docs/testing/manual-test-plan.md`.
