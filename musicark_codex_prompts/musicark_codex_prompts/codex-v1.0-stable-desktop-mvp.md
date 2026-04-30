# codex-v1.0-stable-desktop-mvp

Версия: [[v1.0-stable-desktop-mvp]]

Предыдущая версия: [[v0.11-restore-upload-experimental]]

Следующая версия: [[v1.1-android-mvp]]

Связанные модули:

- [[core]]
- [[providers]]
- [[yandex-music-provider]]
- [[local-library-provider]]
- [[download-system]]
- [[local-archive]]
- [[matching-engine]]
- [[sync-planner]]
- [[sync-executor]]
- [[metadata-engine]]
- [[ui]]
- [[platform-bridge]]
- [[storage]]
- [[history-audit-log]]
- [[risks]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v1.0-stable-desktop-mvp]].

Цель: Стабилизировать первую Windows-версию как usable MVP.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- ревизия модулей;
- основной сценарий auth->scan->archive->download->local scan->matching->sync plan->safe ops->logs;
- миграции;
- ошибки;
- пустые состояния UI;
- smoke/integration tests;
- README;
- инструкция запуска;

## Что нельзя делать

- не добавляй torrent;
- не добавляй новые сервисы;
- не делай Android;
- не делай плеер;
- не раздувай MVP;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
