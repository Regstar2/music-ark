# canonical-library

## Назначение

Внутренняя нормализованная модель музыкальной коллекции.

## Отвечает за

- объединять разные представления одного трека;
- связывать [[track]] с несколькими [[track-source]];
- связывать [[track]] с несколькими [[local-audio-file]];
- служить основой для [[matching-engine]] и [[sync-planner]];
- не зависеть от конкретного музыкального сервиса;

## Связи

- [[canonical-library]] -> [[track]]
- [[canonical-library]] -> [[track-source]]
- [[canonical-library]] -> [[local-audio-file]]
- [[canonical-library]] -> [[matching-engine]]
- [[canonical-library]] -> [[sync-planner]]
- [[canonical-library]] -> [[storage]]

## Примечания

Один трек может иметь источник в Яндекс Музыке, локальный файл, будущий Spotify-провайдер и torrent-импорт. Всё это должно сходиться в одной универсальной модели.
