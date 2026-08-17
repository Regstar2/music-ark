# Content labels — ОРИГИНАЛ / ЦЕНЗУРА

`[[content-labels]]` — пользовательская классификация версии содержимого трека. Она не является частью `[[matching-engine]]`, `[[metadata-engine]]` или `[[variant-detection]]` и не меняет файлы или данные провайдера.

## Назначение

MusicArk хранит одну из двух явных пометок:

- `original` → **ОРИГИНАЛ**;
- `censored` → **ЦЕНЗУРА**.

Пометка необязательна и может быть снята.

## Идентичность

Для локальных треков пометка привязана к `local_file_id`. Обычное повторное сканирование сохраняет ID существующего файла, поэтому пометка переживает переиндексацию.

Для Яндекс Музыки пометка привязана к `(provider_id, external_id)`. Один Track ID получает одну пометку независимо от того, находится он в Liked, одном или нескольких playlist.

## Границы

- локальный MP3/FLAC/WAV и его теги не переписываются;
- Яндекс Музыка не изменяется;
- пометка не повышает confidence Matching и не создаёт Exact identity;
- пометка не меняет Coverage/Missing;
- хранение выполняется только в SQLite MusicArk.

## API

`src/musicark/content_labels/` содержит сервис и JSON process bridge. Flutter использует `ContentLabelBridgeClient` для batch-чтения и явной установки/снятия пометки.

Schema `1.8.3` добавляет `local_track_content_labels` и `provider_track_content_labels` поверх `1.8.2` metadata/artwork cache.
