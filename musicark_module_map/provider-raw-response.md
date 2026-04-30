# provider-raw-response

## Назначение

Безопасное хранение исходных ответов провайдера для отладки и повторного маппинга.

## Отвечает за

- хранить provider raw payload отдельно от нормализованных моделей;
- не хранить токены и auth headers;
- связывать raw payload с типом ответа и временем скана;
- помогать отлаживать изменения неофициального API.

## Связи

- [[provider-raw-response]] -> [[yandex-music-provider]]
- [[provider-raw-response]] -> [[storage]]
- [[provider-raw-response]] -> [[unofficial-api-risk]]
- [[provider-raw-response]] -> [[provider-scan]]

## Реализация v0.3

В `v0.3-yandex-scan` raw responses сохраняются в таблицу
`provider_raw_responses` через `ProviderStorageRepository.insert_raw_response(...)`.
