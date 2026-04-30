# track

## Назначение

Музыкальная сущность в общем виде. Это композиция как объект коллекции, а не файл и не трек конкретного сервиса.

## Отвечает за

- хранить нормализованные музыкальные данные;
- быть связующим центром между [[track-source]] и [[local-audio-file]];
- не знать, как файл был получен;
- не хранить API-логику провайдеров;

## Возможные поля

- id;
- title;
- artists;
- album;
- duration;
- year;
- genre;
- isrc;
- explicit;
- normalized_title;
- normalized_artists;

## Связи

- [[track]] -> [[track-source]]
- [[track]] -> [[local-audio-file]]
- [[track]] -> [[canonical-library]]
- [[track]] -> [[matching-engine]]
- [[track]] -> [[metadata-engine]]

## Правила

[[track]] не равен [[local-audio-file]]. Один трек может иметь несколько файлов: разные качества, версии, remaster, explicit/censored.
