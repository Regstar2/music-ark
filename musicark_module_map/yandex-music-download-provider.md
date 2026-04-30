# yandex-music-download-provider

## Назначение

Download backend для скачивания доступных треков из Яндекс Музыки.

## Отвечает за

- получать [[download-task]] для трека Яндекс Музыки;
- запрашивать данные скачивания через [[yandex-music-provider]];
- выбирать качество;
- скачивать файл;
- сохранять файл в [[local-archive]];
- создавать [[local-audio-file]];
- логировать результат;

## Связи

- [[yandex-music-download-provider]] -> [[download-provider]]
- [[yandex-music-download-provider]] -> [[yandex-music-provider]]
- [[yandex-music-download-provider]] -> [[download-task]]
- [[yandex-music-download-provider]] -> [[local-audio-file]]
- [[yandex-music-download-provider]] -> [[local-archive]]
- [[yandex-music-download-provider]] -> [[history-audit-log]]
- [[yandex-music-download-provider]] -> [[unofficial-api-risk]]

## Правила

UI не должен напрямую вызывать скачивание Яндекс-трека. UI создаёт действие, дальше работает [[download-system]].
