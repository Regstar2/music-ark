# local-audio-file

## Назначение

Физический аудиофайл в локальной медиатеке.

## Отвечает за

- хранить путь к файлу;
- хранить технические параметры;
- хранить хеш и, возможно, аудио-отпечаток;
- хранить метаданные;
- ссылаться на исходный [[download-task]];
- связываться с [[track]] через [[matching-engine]];

## Возможные поля

- id;
- path;
- sha256;
- fingerprint;
- codec;
- bitrate;
- sample_rate;
- duration;
- file_size;
- metadata_json;
- cover_path;
- origin_download_task_id;
- linked_track_id;

## Связи

- [[local-audio-file]] -> [[track]]
- [[local-audio-file]] -> [[track-source]]
- [[local-audio-file]] -> [[download-task]]
- [[local-audio-file]] -> [[local-archive]]
- [[local-audio-file]] -> [[metadata-engine]]
- [[local-audio-file]] -> [[matching-engine]]
- [[local-audio-file]] -> [[storage]]
