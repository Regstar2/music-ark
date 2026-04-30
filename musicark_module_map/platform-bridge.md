# platform-bridge

## Назначение

Слой связи между UI и Python-ядром.

## Отвечает за

- скрывать различия Windows и Android;
- передавать команды из Flutter UI в Python core;
- возвращать результаты и ошибки;
- не содержать бизнес-логику;
- не принимать решений о синхронизации;

## Связи

- [[platform-bridge]] -> [[ui]]
- [[platform-bridge]] -> [[core]]
- [[platform-bridge]] -> [[platforms]]
- [[platform-bridge]] -> [[storage]]

## Примечания

Windows: Flutter -> Python sidecar -> Python core. Android: Flutter -> Kotlin bridge -> embedded Python -> Python core.
