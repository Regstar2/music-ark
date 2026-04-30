# track-source

## Назначение

Описание источника, из которого известен или получен трек.

## Отвечает за

- хранить связь трека с сервисом, локальным файлом, torrent, ручным импортом или будущим источником;
- хранить external_id и raw_data конкретного источника;
- позволять не привязывать архитектуру к Яндекс ID;
- служить входом для [[download-task]], если источник можно скачать;

## Возможные поля

- id;
- track_id;
- source_type;
- provider_id;
- external_id;
- url;
- raw_data;
- availability;
- first_seen_at;
- last_seen_at;

## Связи

- [[track-source]] -> [[track]]
- [[track-source]] -> [[providers]]
- [[track-source]] -> [[download-task]]
- [[track-source]] -> [[local-audio-file]]
- [[track-source]] -> [[storage]]
- [[track-source]] -> [[sync-planner]]

## Примечания

Примеры source_type: yandex_music, local_file, torrent, manual_import, http, future_provider.

## Реализация v0.2

`TrackSource` реализован в `src/musicark/providers/models.py` и сохраняется в
SQLite таблице `track_sources` через `ProviderStorageRepository`.
