# local-library-provider

## Назначение

Провайдер локальной музыкальной библиотеки пользователя.

## Отвечает за

- сканирование папок с музыкой;
- создание [[local-audio-file]];
- чтение метаданных через [[metadata-engine]];
- вычисление хешей;
- определение формата и длительности;
- создание локального [[track-source]];
- передача файлов в [[matching-engine]];

## Связи

- [[local-library-provider]] -> [[providers]]
- [[local-library-provider]] -> [[local-archive]]
- [[local-library-provider]] -> [[local-audio-file]]
- [[local-library-provider]] -> [[metadata-engine]]
- [[local-library-provider]] -> [[matching-engine]]
- [[local-library-provider]] -> [[storage]]

## Примечания

Локальная библиотека — основа сохранности коллекции. Сервисы меняются, файлы остаются, если пользователь не устроил сам себе цифровую амнезию.

## Реализация v0.4

В `v0.4-local-library` добавлен `LocalLibraryProvider` в `src/musicark/providers/local_library.py`:

- рекурсивно сканирует каталог;
- индексирует `mp3/flac/m4a/aac/ogg/wav`;
- вычисляет `sha256` и размер файла;
- читает базовую длительность/метаданные (best-effort);
- создаёт локальный `TrackSource` типа `local_file`;
- пишет scan event в [[history-audit-log]].
