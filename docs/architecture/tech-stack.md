# Технологический стек

## v0.5.1

- Flutter — Windows desktop UI;
- Dart `^3.11.5` — UI runtime;
- Python `>=3.10` — application/provider/local/matching/variant runtime;
- SQLite — Yandex cache, Local Library index, identity matching and variant results;
- `yandex-music==3.0.0` — Yandex Music provider integration;
- `keyring==25.7.0` — системный credential store для Yandex token;
- `mutagen>=1.47.0` — read-only local audio metadata extraction;
- `requests>=2.32.0` — Python HTTP dependency used by network/provider code;
- ffmpeg — **optional external runtime capability** for decoded-audio comparison.

## Identity matching stack

v0.5 не добавляет внешнюю fuzzy-matching библиотеку. Title similarity использует Python stdlib `difflib.SequenceMatcher`; deterministic normalization — `unicodedata`/`re`; candidate lookup и persistence — SQLite.

`MATCHED / CONFLICT / UNMATCHED` и identity confidence остаются отдельными от variant analysis.

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

## ffmpeg failure model

ffmpeg не является hard dependency приложения. Если executable не найден:

- Yandex flow работает;
- Local Library работает;
- v0.5 identity matching работает;
- metadata-level variant evidence работает;
- deep audio verification возвращает безопасный `NOT_CHECKED`/консервативный результат;
- UI явно показывает отсутствие audio verification.

## Persistence boundaries

### Secrets

Yandex token хранится через `keyring` и не записывается в SQLite.

### Yandex cache

`provider_collection_snapshots/items` хранит cache-first библиотеку. Для matching membership материализуется в уникальные `provider_tracks` по `(provider_id, external_id)`.

### Local Library

`local_audio_files` хранит structured tags/technical fields и compact matching index columns. Аудиофайлы остаются read-only.

### Identity Matching

`matching_results`, `track_links` и расширенный `match_conflicts` хранят current identity result, confirmed links, ranked candidates, score breakdown, matcher version и manual decisions.

### Variant Detection

`track_variant_results` хранит только analytical results: status, metadata evidence, audio similarity, reasons, altered regions, fingerprints, analyzer version и reference path. PCM там нет.

## Зафиксированные версии

Фактические ограничения находятся в:

- `pyproject.toml`;
- `requirements-yandex.txt`;
- `ui/musicark_ui/pubspec.yaml`.

ffmpeg устанавливается отдельно и обнаруживается через PATH; его отсутствие не препятствует запуску MusicArk.

## Не входит в v0.5.1

- automatic reference download;
- external fingerprint/matching API;
- ML-based audio recognition;
- download product flow;
- Missing Tracks workflow;
- sync;
- playback/player;
- destructive file operations;
- guaranteed lyric/censorship recognition.

## Тестирование

```powershell
python -m unittest discover -s tests -v
cd ui\musicark_ui
flutter analyze
flutter test
```

## Запуск

```powershell
cd ui\musicark_ui
flutter run -d windows
```
