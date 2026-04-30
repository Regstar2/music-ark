# core

## Назначение

Центральная логика приложения. Не зависит от конкретного сервиса, UI, платформы или способа загрузки файлов.

## Отвечает за

- работать с универсальными сущностями [[track]], [[track-source]], [[local-audio-file]];
- координировать [[canonical-library]], [[matching-engine]], [[sync-planner]] и [[sync-executor]];
- передавать операции в [[download-system]];
- использовать [[storage]] для состояния и истории;
- не содержать UI-логику и платформенные детали;

## Связи

- [[core]] -> [[canonical-library]]
- [[core]] -> [[providers]]
- [[core]] -> [[download-system]]
- [[core]] -> [[storage]]
- [[core]] -> [[matching-engine]]
- [[core]] -> [[sync-planner]]
- [[core]] -> [[sync-executor]]
- [[core]] -> [[metadata-engine]]
- [[core]] -> [[history-audit-log]]

## Правила

В [[core]] не должно быть условий уровня `if android` или `if yandex`. Иначе универсальность тихо умирает, а потом делает вид, что так и было задумано.

## Реализация v0.1

В `v0.1-core-foundation` модуль реализован в `src/musicark/core/` и включает:

- `MusicArkApp` как минимальный composition root;
- `AppConfig` + загрузку/сохранение конфигурации;
- базовые доменные исключения;
- инициализацию логирования для CLI.
