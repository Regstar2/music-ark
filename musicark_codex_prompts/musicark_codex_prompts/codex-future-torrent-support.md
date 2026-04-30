# codex-future-torrent-support

Версия: [[future-torrent-support]]

Предыдущая версия: [[v1.0-stable-desktop-mvp]]

Связанные модули:

- [[torrent-download-provider]]
- [[download-system]]
- [[download-task]]
- [[download-provider]]
- [[download-queue-ui]]
- [[local-archive]]
- [[local-audio-file]]
- [[matching-engine]]
- [[conflict-resolver]]
- [[history-audit-log]]
- [[torrent-misuse-risk]]
- [[legal-terms-risk]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[future-torrent-support]].

Цель: Добавить BitTorrent как отдельный [[download-provider]] для легального пополнения локальной медиатеки.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- выбор torrent engine;
- [[torrent-download-provider]];
- task типа torrent;
- импорт .torrent/magnet;
- список файлов;
- выбор файлов;
- фильтр аудио;
- progress;
- создание [[local-audio-file]];
- matching;
- conflicts;
- UI queue;
- документация ограничений;

## Что нельзя делать

- не добавляй публичную базу ссылок;
- не делай поиск коммерческих треков;
- не делай каталог;
- не привязывай torrent к Яндексу;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
