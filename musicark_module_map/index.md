# MusicArk — карта модулей

## Назначение

Главная навигационная заметка по модульной структуре MusicArk. Используй её как входную точку для Obsidian Canvas и как список узлов карты проекта.

## Отвечает за

- зафиксировать основные модули приложения;
- показать связи между модулями;
- отделить универсальное ядро от Яндекс Музыки;
- заложить место для будущих провайдеров и BitTorrent как отдельного download backend;

## Связи

- [[index]] -> [[core]]
- [[index]] -> [[providers]]
- [[index]] -> [[download-system]]
- [[index]] -> [[local-archive]]
- [[index]] -> [[storage]]
- [[index]] -> [[ui]]
- [[index]] -> [[platforms]]
- [[index]] -> [[risks]]
- [[index]] -> [[canonical-library]]
- [[index]] -> [[track]]
- [[index]] -> [[track-source]]
- [[index]] -> [[local-audio-file]]
- [[index]] -> [[matching-engine]]
- [[index]] -> [[sync-planner]]
- [[index]] -> [[sync-executor]]
- [[index]] -> [[metadata-engine]]
- [[index]] -> [[conflict-resolver]]
- [[index]] -> [[history-audit-log]]
- [[index]] -> [[provider-capabilities]]
- [[index]] -> [[yandex-music-provider]]
- [[index]] -> [[local-library-provider]]
- [[index]] -> [[future-providers]]
- [[index]] -> [[download-task]]
- [[index]] -> [[download-provider]]
- [[index]] -> [[yandex-music-download-provider]]
- [[index]] -> [[torrent-download-provider]]
- [[index]] -> [[local-import-provider]]
- [[index]] -> [[platform-bridge]]
- [[index]] -> [[download-queue-ui]]

## Примечания

MusicArk архитектурно универсален, но первая реализация будет вокруг [[yandex-music-provider]] и [[local-library-provider]].

Музыкальный сервис не должен быть центром архитектуры. Центр — [[canonical-library]], [[track-source]], [[local-audio-file]], [[sync-planner]] и [[storage]].

Скачивание должно идти через [[download-system]], а не через прямые вызовы из UI или Core.
