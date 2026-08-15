# Технологический стек

## v0.6.0

- Flutter — Windows desktop UI;
- Dart `^3.11.5` — UI runtime;
- Python `>=3.10` — application/provider/local/matching/variant/coverage runtime;
- SQLite — Yandex cache, Local Library index, identity matching, variant results и coverage triage;
- `yandex-music==3.0.0` — Yandex Music provider integration;
- `keyring==25.7.0` — системный credential store для Yandex token;
- `mutagen>=1.47.0` — read-only local audio metadata extraction;
- `requests>=2.32.0` — Python HTTP dependency used by network/provider code;
- ffmpeg — **optional external runtime capability** for v0.5.1 decoded-audio comparison.

## Identity matching stack

v0.5 не добавляет внешнюю fuzzy-matching библиотеку. Title similarity использует Python stdlib `difflib.SequenceMatcher`; deterministic normalization — `unicodedata`/`re`; candidate lookup и persistence — SQLite.

`MATCHED / CONFLICT / UNMATCHED` и identity confidence остаются отдельными от variant analysis и v0.6 coverage.

## Variant / audio stack

v0.5.1 также не добавляет внешний matching/fingerprint API и не добавляет ML stack.

`FfmpegAudioDecoder` приводит MP3/FLAC/другие поддерживаемые ffmpeg форматы к одному PCM-представлению:

```text
mono · signed 16-bit · 11025 Hz
```

PCM читается через pipe. Временные WAV не нужны, аудио blobs в SQLite не записываются.

Сравнение реализовано локально на Python stdlib:

- coarse energy-envelope correlation для bounded alignment;
- overlapping segment windows;
- RMS/energy envelope;
- compact Goertzel spectral measurements;
- zero-crossing / waveform-derivative signals;
- cosine/scalar normalized similarity;
- region merging;
- policy-based classifier.

Это позволяет не добавлять NumPy/PyTorch/TensorFlow только ради v0.5.1.

## Coverage stack

v0.6 не добавляет второй matching engine и не добавляет analytics framework. `LibraryCoverageService` использует SQL-backed `CoverageRepository` поверх existing authoritative tables.

Summary/list/filter/search/sort/pagination выполняются через SQLite CTE, `JOIN`, `LEFT JOIN`, `EXISTS` и существующие/новые indexes. Coverage status не materialize-ится в отдельную `missing_tracks` таблицу и не вычисляется во Flutter по всей библиотеке.

Три persistence boundary остаются независимыми:

```text
matching_results / track_links  → identity truth
track_variant_results           → secondary recording truth
provider_track_actions          → wanted / ignored user triage
```

## ffmpeg failure model

ffmpeg не является hard dependency приложения. Если executable не найден:

- Yandex flow работает;
- Local Library работает;
- v0.5 identity matching работает;
- v0.6 Coverage работает;
- metadata-level variant evidence работает;
- deep audio verification возвращает безопасный `NOT_CHECKED`/консервативный результат;
- UI явно показывает отсутствие audio verification.

## Persistence boundaries

### Secrets

Yandex token хранится через `keyring` и не записывается в SQLite.

### Yandex cache

`provider_collection_snapshots/items` хранит cache-first библиотеку. Для matching membership материализуется в уникальные `provider_tracks` по canonical `(provider_id, external_id)`. v0.6 также использует active collection membership как начало coverage query.

### Local Library

`local_audio_files` хранит structured tags/technical fields и compact matching index columns. Аудиофайлы остаются read-only.

### Identity Matching

`matching_results`, `track_links` и расширенный `match_conflicts` хранят current identity result, confirmed links, ranked candidates, score breakdown, matcher version и manual decisions.

### Variant Detection

`track_variant_results` хранит только analytical results: status, metadata evidence, audio similarity, reasons, altered regions, fingerprints, analyzer version и reference path. PCM там нет.

### Coverage triage

`provider_track_actions` хранит только `wanted` или `ignored`; отсутствие row означает `unreviewed`. Technical coverage derived и не дублируется.

## Reference boundary

Актуальная v0.5.1 реализация может bounded-способом получить один exact reference во время explicit single-track verification. Этот cache verification-only: он не индексируется автоматически в Local Library и не создаёт `track_links`, поэтому не влияет на covered/missing сам по себе.

## Зафиксированные версии

Фактические ограничения находятся в:

- `pyproject.toml`;
- `requirements-yandex.txt`;
- `ui/musicark_ui/pubspec.yaml`.

ffmpeg устанавливается отдельно и обнаруживается через PATH; его отсутствие не препятствует запуску MusicArk.

## Не входит в v0.6

- Missing Tracks download execution;
- download source selection / torrent / YouTube flow;
- external fingerprint/matching API;
- ML-based audio recognition;
- sync execution;
- playback/player;
- destructive file operations;
- Yandex mutation;
- guaranteed lyric/censorship recognition.

## Тестирование

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
cd ui\musicark_ui
flutter analyze
flutter test
```

## Запуск

```powershell
cd ui\musicark_ui
flutter run -d windows
```
