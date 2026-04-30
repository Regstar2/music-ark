# local-import-provider

## Назначение

Download backend для ручного импорта уже существующих локальных файлов.

## Отвечает за

- принимать выбранные пользователем файлы или папки;
- проверять аудиоформат;
- создавать [[local-audio-file]];
- читать метаданные через [[metadata-engine]];
- вычислять хеш;
- создавать локальный [[track-source]];
- передавать файл в [[matching-engine]];

## Связи

- [[local-import-provider]] -> [[download-provider]]
- [[local-import-provider]] -> [[download-task]]
- [[local-import-provider]] -> [[local-audio-file]]
- [[local-import-provider]] -> [[local-archive]]
- [[local-import-provider]] -> [[metadata-engine]]
- [[local-import-provider]] -> [[matching-engine]]
- [[local-import-provider]] -> [[storage]]

## Примечания

Ручной импорт должен использовать ту же модель задач, что и скачивание. Да, даже если файл уже на диске. Унификация иногда не враг, а санитар.
