# conflict-resolver

## Назначение

Модуль ручного решения спорных ситуаций.

## Отвечает за

- показывать пользователю кандидаты совпадения;
- позволять подтвердить или отклонить связь;
- объединять дубли;
- разделять ошибочные связи;
- выбирать нужный файл из torrent-раздачи;
- сохранять решения пользователя;

## Связи

- [[conflict-resolver]] -> [[matching-engine]]
- [[conflict-resolver]] -> [[sync-planner]]
- [[conflict-resolver]] -> [[local-audio-file]]
- [[conflict-resolver]] -> [[track]]
- [[conflict-resolver]] -> [[ui]]
- [[conflict-resolver]] -> [[history-audit-log]]
- [[conflict-resolver]] -> [[storage]]

## Примечания

Если пользователь уже решил конфликт, приложение должно это запомнить. Иначе оно не помощник, а попугай с базой SQLite.
