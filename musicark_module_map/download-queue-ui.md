# download-queue-ui

## Назначение

Экран очереди загрузок и импортов.

## Отвечает за

- показывать активные, ожидающие, завершённые и failed-задачи;
- показывать прогресс и ошибки;
- давать паузу, отмену и повтор;
- открывать результат как [[local-audio-file]];
- отправлять спорные результаты в [[conflict-resolver]];

## Связи

- [[download-queue-ui]] -> [[ui]]
- [[download-queue-ui]] -> [[download-system]]
- [[download-queue-ui]] -> [[download-task]]
- [[download-queue-ui]] -> [[download-provider]]
- [[download-queue-ui]] -> [[local-audio-file]]
- [[download-queue-ui]] -> [[history-audit-log]]

## Примечания

Очередь должна быть общей для Яндекс Музыки, torrent и локального импорта. Отдельные очереди — это зоопарк одинаковых таблиц с разными багами.
