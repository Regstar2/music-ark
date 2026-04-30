# codex-v0.2-provider-architecture

Версия: [[v0.2-provider-architecture]]

Предыдущая версия: [[v0.1-core-foundation]]

Следующая версия: [[v0.3-yandex-scan]]

Связанные модули:

- [[providers]]
- [[provider-capabilities]]
- [[track-source]]
- [[yandex-music-provider]]
- [[local-library-provider]]
- [[future-providers]]
- [[storage]]
- [[core]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.2-provider-architecture]].

Цель: Заложить универсальную архитектуру провайдеров.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- MusicProvider;
- [[provider-capabilities]];
- ProviderRegistry;
- ProviderTrack/ProviderPlaylist;
- [[track-source]];
- заглушки [[yandex-music-provider]] и [[local-library-provider]];
- сохранение provider metadata;
- тесты registry/capabilities;

## Что нельзя делать

- не подключай реальный API;
- не делай скачивание;
- не смешивай [[providers]] и [[download-provider]];

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
