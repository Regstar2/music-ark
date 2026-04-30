# torrent-download-provider

## Назначение

Будущий download backend для получения файлов через BitTorrent.

## Отвечает за

- импорт пользовательских .torrent файлов;
- импорт magnet-ссылок;
- выбор файлов внутри раздачи;
- загрузка выбранных аудиофайлов;
- создание [[local-audio-file]];
- передача результата в [[matching-engine]];
- отправка спорных случаев в [[conflict-resolver]];
- логирование torrent-задач;

## Связи

- [[torrent-download-provider]] -> [[download-provider]]
- [[torrent-download-provider]] -> [[download-system]]
- [[torrent-download-provider]] -> [[download-task]]
- [[torrent-download-provider]] -> [[local-audio-file]]
- [[torrent-download-provider]] -> [[local-archive]]
- [[torrent-download-provider]] -> [[matching-engine]]
- [[torrent-download-provider]] -> [[conflict-resolver]]
- [[torrent-download-provider]] -> [[torrent-misuse-risk]]

## Правила

MusicArk не должен поставляться с публичной базой torrent/magnet-ссылок на коммерческие треки. Пользователь сам добавляет источники и сам отвечает за их легальность.
