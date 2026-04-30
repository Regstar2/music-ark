# upload-uncertainty-risk

## Назначение

Риск неопределённости загрузки пользовательских треков в Яндекс Музыку.

## Отвечает за

- не включать upload как обязательный MVP;
- держать upload как experimental;
- проектировать восстановление через [[track-source]] и [[local-audio-file]];
- сохранять replacement mappings в [[storage]];

## Связи

- [[upload-uncertainty-risk]] -> [[yandex-music-provider]]
- [[upload-uncertainty-risk]] -> [[sync-planner]]
- [[upload-uncertainty-risk]] -> [[sync-executor]]
- [[upload-uncertainty-risk]] -> [[local-audio-file]]
- [[upload-uncertainty-risk]] -> [[storage]]
