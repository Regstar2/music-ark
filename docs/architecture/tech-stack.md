# Технологический стек

## v0.5.0

- Flutter — Windows desktop UI;
- Dart `^3.11.5` — UI runtime;
- Python `>=3.10` — application/provider/local/matching runtime;
- SQLite — Yandex cache, Local Library index, canonical links and matching results;
- `yandex-music==3.0.0` — Yandex Music provider integration;
- `keyring==25.7.0` — системный credential store для Yandex token;
- `mutagen>=1.47.0` — read-only local audio metadata extraction;
- `requests>=2.32.0` — Python HTTP dependency used by network/provider code.

## Matching stack

v0.5 не добавляет внешнюю fuzzy-matching библиотеку. Title similarity использует Python stdlib `difflib.SequenceMatcher`; deterministic normalization — `unicodedata`/`re`; candidate lookup и persistence — SQLite.

Это сохраняет matching полностью локальным и не добавляет runtime network dependency.

## Persistence boundaries

### Secrets

Yandex token хранится через `keyring` и не записывается в SQLite.

### Yandex cache

`provider_collection_snapshots/items` хранит cache-first библиотеку. Для matching membership материализуется в уникальные `provider_tracks` по `(provider_id, external_id)`.

### Local Library

`local_audio_files` хранит structured tags/technical fields и compact matching index columns. Аудиофайлы остаются read-only.

### Matching

`matching_results`, `track_links` и расширенный `match_conflicts` хранят current result, confirmed links, ranked candidates, score breakdown, matcher version и manual decisions.

## Зафиксированные версии

Фактические ограничения находятся в:

- `pyproject.toml`;
- `requirements-yandex.txt`;
- `ui/musicark_ui/pubspec.yaml`.

## Не входит в v0.5

- download;
- Missing Tracks workflow;
- sync;
- metadata editor;
- playback/player;
- file rename/move/delete;
- standalone Python bundling/installer.

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
