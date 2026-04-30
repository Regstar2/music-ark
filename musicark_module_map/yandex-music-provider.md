# yandex-music-provider

## Назначение

Первый реальный музыкальный провайдер MusicArk. Работает с Яндекс Музыкой через неофициальную Python-библиотеку.

## Отвечает за

- авторизация по токену;
- сканирование лайкнутых треков;
- сканирование пользовательских плейлистов;
- получение информации о треках;
- определение доступности треков;
- создание [[track-source]] для данных Яндекс Музыки;
- передача задач скачивания в [[download-system]];
- экспериментальная загрузка пользовательских треков, если технически возможно;

## Связи

- [[yandex-music-provider]] -> [[providers]]
- [[yandex-music-provider]] -> [[provider-capabilities]]
- [[yandex-music-provider]] -> [[track-source]]
- [[yandex-music-provider]] -> [[yandex-music-download-provider]]
- [[yandex-music-provider]] -> [[download-system]]
- [[yandex-music-provider]] -> [[sync-planner]]
- [[yandex-music-provider]] -> [[storage]]
- [[yandex-music-provider]] -> [[unofficial-api-risk]]
- [[yandex-music-provider]] -> [[upload-uncertainty-risk]]
- [[yandex-music-provider]] -> [[account-limits-risk]]
- [[yandex-music-provider]] -> [[legal-terms-risk]]

## Правила

Яндекс Музыка — первый сценарий, но не центр вселенной. Архитектурно это просто один из [[providers]].
