# codex-v0.5-download-system

Версия: [[v0.5-download-system]]

Предыдущая версия: [[v0.4-local-library]]

Следующая версия: [[v0.6-yandex-download]]

Связанные модули:

- [[download-system]]
- [[download-task]]
- [[download-provider]]
- [[local-import-provider]]
- [[local-audio-file]]
- [[local-archive]]
- [[storage]]
- [[history-audit-log]]
- [[torrent-download-provider]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.5-download-system]].

Цель: Вынести получение файлов в универсальный [[download-system]].


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- [[download-task]];
- статусы pending/queued/running/paused/completed/failed/cancelled/needs_review;
- [[download-provider]];
- registry;
- очередь;
- progress/error/retry/cancel;
- [[local-import-provider]];
- task->source->file;
- CLI download/import;
- тесты;

## Что нельзя делать

- не реализуй [[yandex-music-download-provider]];
- не реализуй [[torrent-download-provider]];
- не делай sync;
- не делай UI;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
