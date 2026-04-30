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
