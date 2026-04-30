# codex-v0.6-yandex-download

Версия: [[v0.6-yandex-download]]

Предыдущая версия: [[v0.5-download-system]]

Следующая версия: [[v0.7-matching]]

Связанные модули:

- [[yandex-music-download-provider]]
- [[yandex-music-provider]]
- [[download-system]]
- [[download-task]]
- [[download-provider]]
- [[local-archive]]
- [[local-audio-file]]
- [[history-audit-log]]
- [[unofficial-api-risk]]
- [[account-limits-risk]]

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.6-yandex-download]].

Цель: Скачивать доступные треки Яндекс Музыки через [[download-system]].


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- [[yandex-music-download-provider]];
- task для yandex_music source;
- скачивание одного трека;
- пакетные задачи;
- качество если доступно;
- retry;
- сохранение в [[local-archive]];
- создание [[local-audio-file]];
- связи ProviderTrack->source->task->file;
- CLI;
- тесты без сети;

## Что нельзя делать

- не вызывай download из UI;
- не делай upload;
- не делай matching;
- не делай torrent;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
