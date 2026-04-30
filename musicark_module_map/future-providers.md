# future-providers

## Назначение

Будущие адаптеры к другим музыкальным сервисам.

## Отвечает за

- подключаться через общий слой [[providers]];
- объявлять возможности через [[provider-capabilities]];
- создавать [[track-source]];
- использовать [[canonical-library]] для связей с локальной коллекцией;
- не требовать переписывания [[core]];

## Связи

- [[future-providers]] -> [[providers]]
- [[future-providers]] -> [[provider-capabilities]]
- [[future-providers]] -> [[track-source]]
- [[future-providers]] -> [[canonical-library]]
- [[future-providers]] -> [[matching-engine]]
- [[future-providers]] -> [[sync-planner]]

## Примечания

Возможные сервисы: YouTube Music, Spotify, SoundCloud, VK Music, Apple Music, Deezer. Не все из них обязаны уметь скачивание или загрузку.
