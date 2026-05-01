# metadata-engine

## Назначение

Модуль чтения, редактирования и нормализации метаданных локальных аудиофайлов.

## Отвечает за

- читать теги;
- записывать теги;
- изменять название, исполнителя, альбом, год, жанр и номер трека;
- работать с обложками;
- нормализовать имена файлов;
- помогать [[matching-engine]];
- подготавливать метаданные перед загрузкой;

## Связи

- [[metadata-engine]] -> [[local-audio-file]]
- [[metadata-engine]] -> [[local-archive]]
- [[metadata-engine]] -> [[matching-engine]]
- [[metadata-engine]] -> [[local-library-provider]]
- [[metadata-engine]] -> [[ui]]
- [[metadata-engine]] -> [[history-audit-log]]

## Правила

Массовое изменение метаданных должно попадать в [[history-audit-log]]. Иначе пользователь потом будет искать виноватого, а виноватым окажется приложение. Неловко.

## Реализация (обновление v0.10)

Исходный код:

- `src/musicark/metadata/engine.py` — чтение/запись тегов (mutagen: MP3, FLAC, MP4/M4A, AAC, OGG; WAV только читается без тегового редактора).
- `src/musicark/metadata/service.py` — согласование с SQLite [[storage]], резервные копии `.musicark/metadata_backups/` и [[history-audit-log]].

Публичные команды для [[platform-bridge]]: `metadata_get`, `metadata_update` (поле `"confirm": true` обязательно), `metadata_bulk_update` (≥2 файлов по id).
