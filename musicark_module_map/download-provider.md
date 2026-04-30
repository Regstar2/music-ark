# download-provider

## Назначение

Механизм получения файла. Получает [[download-task]] и пытается создать [[local-audio-file]].

## Отвечает за

- проверить входные данные задачи;
- выполнить загрузку или импорт;
- сообщать прогресс;
- вернуть результат;
- записать ошибку при неудаче;
- не решать глобальную синхронизацию;

## Связи

- [[download-provider]] -> [[download-task]]
- [[download-provider]] -> [[download-system]]
- [[download-provider]] -> [[local-audio-file]]
- [[download-provider]] -> [[local-archive]]
- [[download-provider]] -> [[history-audit-log]]
- [[download-provider]] -> [[yandex-music-download-provider]]
- [[download-provider]] -> [[torrent-download-provider]]
- [[download-provider]] -> [[local-import-provider]]

## Реализация v0.5

В `v0.5-download-system` реализованы:

- интерфейс `DownloadProvider` в `src/musicark/download/provider.py`;
- `LocalImportProvider` как первый рабочий backend через общий download-system;
- отсутствие привязки к Яндекс и torrent backend на этом этапе.
