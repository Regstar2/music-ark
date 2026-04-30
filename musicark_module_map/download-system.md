# download-system

## Назначение

Отдельный слой получения файлов через разные механизмы.

## Отвечает за

- создавать и хранить [[download-task]];
- выбирать подходящий [[download-provider]];
- отслеживать прогресс;
- обрабатывать ошибки;
- передавать результат в [[local-archive]] как [[local-audio-file]];
- обслуживать общий [[download-queue-ui]];

## Связи

- [[download-system]] -> [[download-task]]
- [[download-system]] -> [[download-provider]]
- [[download-system]] -> [[local-audio-file]]
- [[download-system]] -> [[local-archive]]
- [[download-system]] -> [[sync-planner]]
- [[download-system]] -> [[sync-executor]]
- [[download-system]] -> [[history-audit-log]]
- [[download-system]] -> [[download-queue-ui]]

## Правила

Скачивание из Яндекс Музыки, torrent и локальный импорт должны идти через один слой. Иначе появятся три одинаковые очереди загрузок с тремя разными способами сломаться.
