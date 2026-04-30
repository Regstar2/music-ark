# matching-engine

## Назначение

Система сопоставления треков, источников и локальных файлов.

## Отвечает за

- сравнивать название, исполнителей, альбом и длительность;
- использовать ISRC, хеши и аудио-отпечатки при наличии;
- рассчитывать уверенность совпадения;
- создавать связи в [[canonical-library]];
- отправлять спорные случаи в [[conflict-resolver]];

## Связи

- [[matching-engine]] -> [[track]]
- [[matching-engine]] -> [[track-source]]
- [[matching-engine]] -> [[local-audio-file]]
- [[matching-engine]] -> [[canonical-library]]
- [[matching-engine]] -> [[conflict-resolver]]
- [[matching-engine]] -> [[sync-planner]]
- [[matching-engine]] -> [[metadata-engine]]

## Примечания

Лучше отправить сомнительное совпадение на ручную проверку, чем уверенно связать не тот трек. Автоматизация с самоуверенностью — это просто баг в костюме фичи.

## Реализация v0.7

В `v0.7-matching` модуль реализован в `src/musicark/matching/`:

- нормализация title/artists;
- confidence scoring для совпадений source <-> local file;
- автоматическое создание `Track` и `TrackLink` для сильных совпадений;
- спорные совпадения в `match_conflicts` для [[conflict-resolver]];
- CLI `musicark match run/list-conflicts/accept`.
