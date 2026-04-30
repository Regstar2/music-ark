# codex-v0.8-sync-planner

Версия: [[v0.8-sync-planner]]

Предыдущая версия: [[v0.7-matching]]

Следующая версия: [[v0.9-desktop-ui]]

Связанные модули:

- [[sync-planner]]
- [[sync-executor]]
- [[matching-engine]]
- [[canonical-library]]
- [[download-system]]
- [[download-task]]
- [[storage]]
- [[history-audit-log]]
- [[ui]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.8-sync-planner]].

Цель: Строить SyncPlan без выполнения опасных действий.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- SyncPlan/SyncOperation;
- операции download_track/mark_unavailable/link_local/needs_review/update_metadata_candidate/upload_candidate/create_download_task;
- анализ remote_only/local_only/missing_local_copy/remote_unavailable/metadata_changed;
- dry run;
- сохранение;
- CLI sync plan;
- тесты;

## Что нельзя делать

- не выполняй операции сразу;
- не удаляй;
- не делай upload;
- не запускай download без подтверждения;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
