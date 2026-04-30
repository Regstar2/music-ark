# provider-capabilities

## Назначение

Описание возможностей конкретного музыкального провайдера.

## Отвечает за

- сообщать, умеет ли провайдер сканировать библиотеку;
- сообщать, умеет ли провайдер скачивать треки;
- сообщать, умеет ли провайдер загружать пользовательские файлы;
- помогать [[ui]] показывать только доступные действия;
- помогать [[sync-planner]] не строить невозможные операции;

## Возможные поля

- can_authenticate;
- can_scan_library;
- can_scan_playlists;
- can_download_tracks;
- can_upload_tracks;
- can_create_playlists;
- can_edit_playlists;
- supports_track_availability;
- supports_user_uploads;

## Связи

- [[provider-capabilities]] -> [[providers]]
- [[provider-capabilities]] -> [[yandex-music-provider]]
- [[provider-capabilities]] -> [[future-providers]]
- [[provider-capabilities]] -> [[ui]]
- [[provider-capabilities]] -> [[sync-planner]]

## Реализация v0.2

`ProviderCapabilities` реализован как универсальная dataclass-модель в
`src/musicark/providers/models.py` и используется:

- в `MusicProvider.capabilities`;
- в `ProviderRegistry`;
- при сохранении provider metadata в [[storage]].
