# codex-v0.9-desktop-ui

Версия: [[v0.9-desktop-ui]]

Предыдущая версия: [[v0.8-sync-planner]]

Следующая версия: [[v0.10-metadata-editor]]

Связанные модули:

- [[ui]]
- [[platform-bridge]]
- [[core]]
- [[storage]]
- [[download-queue-ui]]
- [[sync-planner]]
- [[download-system]]
- [[conflict-resolver]]
- [[history-audit-log]]
- [[platforms]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.9-desktop-ui]].

Цель: Сделать первую Windows GUI-версию без бизнес-логики в UI.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- Flutter desktop;
- [[platform-bridge]] к Python [[core]];
- Dashboard;
- Collection;
- Local Library;
- Providers;
- [[download-queue-ui]];
- Sync Plan;
- Conflict View;
- Logs;
- Settings;
- запуск сканов;
- loading/progress/errors;

## Что нельзя делать

- не пиши sync-логику в Dart;
- не скачивай напрямую из UI;
- не делай Android;
- не делай torrent;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
