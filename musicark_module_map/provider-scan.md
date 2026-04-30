# provider-scan

## Назначение

Операция получения данных коллекции из внешнего provider в нормализованный формат MusicArk.

## Отвечает за

- запуск auth-check и сканирования provider данных;
- фиксирование времени и результата скана;
- запись нормализованных provider моделей в [[storage]];
- запись scan events в [[history-audit-log]];
- отделение scan логики от sync/download логики.

## Связи

- [[provider-scan]] -> [[providers]]
- [[provider-scan]] -> [[yandex-music-provider]]
- [[provider-scan]] -> [[provider-raw-response]]
- [[provider-scan]] -> [[history-audit-log]]
- [[provider-scan]] -> [[storage]]

## Реализация v0.3

В `v0.3-yandex-scan` скан реализован методом `YandexMusicProvider.scan_all(...)`
и CLI-командами `musicark yandex scan-*`.
