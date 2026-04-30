# codex-future-providers-support

Версия: [[future-providers-support]]

Предыдущая версия: [[v1.0-stable-desktop-mvp]]

Связанные модули:

- [[future-providers]]
- [[providers]]
- [[provider-capabilities]]
- [[track-source]]
- [[canonical-library]]
- [[matching-engine]]
- [[sync-planner]]
- [[ui]]
- [[storage]]
- [[risks]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[future-providers-support]].

Цель: Добавить новый музыкальный сервис через [[providers]].


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- выбери один сервис;
- provider_id;
- [[provider-capabilities]];
- auth;
- scan library/playlists если доступно;
- mapping в ProviderTrack/Playlist;
- [[track-source]];
- raw data;
- matching;
- capabilities в UI;
- sync planner;
- тесты;
- docs;

## Что нельзя делать

- не добавляй download если сервис не поддерживает;
- не обходи ограничения;
- не делай несколько провайдеров сразу;
- не добавляй provider-specific логику в [[core]];

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
