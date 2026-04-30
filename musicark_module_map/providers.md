# providers

## Назначение

Слой адаптеров к музыкальным сервисам и источникам коллекции.

## Отвечает за

- авторизация в сервисах;
- сканирование коллекций и плейлистов;
- получение информации о треках;
- создание [[track-source]];
- объявление возможностей через [[provider-capabilities]];
- не смешиваться с [[download-provider]];

## Связи

- [[providers]] -> [[provider-capabilities]]
- [[providers]] -> [[yandex-music-provider]]
- [[providers]] -> [[local-library-provider]]
- [[providers]] -> [[future-providers]]
- [[providers]] -> [[track-source]]
- [[providers]] -> [[core]]
- [[providers]] -> [[storage]]
- [[providers]] -> [[sync-planner]]

## Правила

[[providers]] описывают сервисы. [[download-provider]] описывает способ получения файла. Перепутать их легко, чинить потом неприятно.

## Реализация v0.2

В `v0.2-provider-architecture` модуль реализован в `src/musicark/providers/`:

- интерфейс `MusicProvider`;
- модели `ProviderTrack`, `ProviderPlaylist`, `TrackSource`;
- `ProviderRegistry` для регистрации и получения провайдеров по `provider_id`;
- заглушки `YandexMusicProviderStub` и `LocalLibraryProviderStub` без реальных API вызовов.
