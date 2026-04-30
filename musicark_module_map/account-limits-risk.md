# account-limits-risk

## Назначение

Риск лимитов, ошибок и ограничений со стороны сервиса.

## Отвечает за

- ограничивать скорость запросов;
- делать batch-операции осторожно;
- сохранять прогресс;
- разрешать повтор операций;
- логировать сбои;

## Связи

- [[account-limits-risk]] -> [[yandex-music-provider]]
- [[account-limits-risk]] -> [[download-system]]
- [[account-limits-risk]] -> [[sync-executor]]
- [[account-limits-risk]] -> [[history-audit-log]]

## Реализация v0.3

На `v0.3-yandex-scan` риск лимитов учитывается через:

- отдельный scan-метод с явными этапами (`account`, `likes`, `playlists`);
- запись scan событий в [[history-audit-log]];
- безопасный повторный запуск с upsert-моделью в [[storage]] без размножения дублей.
