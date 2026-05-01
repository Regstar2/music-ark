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

## Команды (оформление v0.10)

Подкоманда `action`:

- общие флаги: `--name …`, необязательно `--path`, необязательно `--payload '<JSON>'` для действий с аргументами (например [[metadata-engine]] — `metadata_get`, `metadata_update`, `metadata_bulk_update`).
