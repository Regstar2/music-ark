# codex-v0.11-restore-upload-experimental

Версия: [[v0.11-restore-upload-experimental]]

Предыдущая версия: [[v0.10-metadata-editor]]

Следующая версия: [[v1.0-stable-desktop-mvp]]

Связанные модули:

- [[yandex-music-provider]]
- [[sync-planner]]
- [[sync-executor]]
- [[local-audio-file]]
- [[track-source]]
- [[storage]]
- [[history-audit-log]]
- [[upload-uncertainty-risk]]
- [[legal-terms-risk]]

## Контекст реализации (после v0.10)

- Клиент `yandex-music` 3.0.0 **не предоставляет** публичных методов загрузки треков; пробник всегда может возвращать `not_supported` — это допустимо по цели версии («проверить возможность»).
- Флаг `experimental_yandex_upload` хранится в [[AppConfig]] (`.musicark/config.json`), UI: вкладка **Settings** во Flutter.
- Пробы: CLI `musicark yandex experimental-upload --confirm …`, bridge `experimental_yandex_upload` с `--payload`.

# Prompt for Codex

Ты работаешь над MusicArk. Реализуй этап [[v0.11-restore-upload-experimental]].

Цель: Экспериментально проверить upload локальных файлов в Яндекс Музыку.


## Общие правила

- Сначала изучи текущий репозиторий и не ломай уже работающий код.
- Реализуй только текущую версию, будущие версии не делай.
- Бизнес-логика остаётся в [[core]], UI только вызывает команды.
- Все изменения состояния должны логироваться в [[history-audit-log]].
- Добавь или обнови тесты.
- После работы перечисли изменённые файлы, команды проверки, тесты, ограничения и TODO.

## Что нужно сделать

- исследуй upload;
- если есть — upload одного [[local-audio-file]], плейлист восстановленных, uploaded [[track-source]], replacement mapping;
- если нет — not_supported;
- операции upload_candidate/replace_candidate;
- feature flag;
- тесты mapping;

## Что нельзя делать

- не делай массовую замену;
- не удаляй оригиналы без подтверждения;
- не делай upload обязательным для v1.0;

## Критерии готовности

- код собирается/запускается;
- добавлены или обновлены тесты;
- поведение соответствует цели версии;
- будущие версии не реализованы раньше времени;
- документация или README обновлены при необходимости;
- в конце ответа есть отчёт по изменениям.
