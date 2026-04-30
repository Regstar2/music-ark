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
