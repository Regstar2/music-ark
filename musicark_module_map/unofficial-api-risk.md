# unofficial-api-risk

## Назначение

Риск использования неофициального API Яндекс Музыки.

## Отвечает за

- учитывать возможную поломку методов;
- изолировать Яндекс-логику в [[yandex-music-provider]];
- не размазывать вызовы API по [[core]] и [[ui]];
- логировать ошибки и raw responses;

## Связи

- [[unofficial-api-risk]] -> [[yandex-music-provider]]
- [[unofficial-api-risk]] -> [[yandex-music-download-provider]]
- [[unofficial-api-risk]] -> [[upload-uncertainty-risk]]
- [[unofficial-api-risk]] -> [[account-limits-risk]]
- [[unofficial-api-risk]] -> [[history-audit-log]]
- [[unofficial-api-risk]] -> [[storage]]
