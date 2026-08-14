# Scope MVP

## Цель

Доказать один рабочий end-to-end сценарий: `запуск -> токен -> аккаунт -> Мне нравится`.

## Входит

- один основной экран;
- форма токена;
- проверка токена через существующий `YandexMusicProvider`;
- запрос лайков без SQLite;
- список треков;
- refresh;
- logout;
- обработка ошибок bridge;
- Python и Flutter автоматические тесты;
- команды setup/run/test/build в README.

## Не входит

- legacy dashboard;
- download queue;
- sync planner/executor;
- metadata editor;
- local library UI;
- conflicts UI;
- experimental upload;
- persistent token storage;
- автономная упаковка Python.

## Разрешённые модули текущего перезапуска

- новый MVP bridge;
- Flutter desktop UI;
- тесты MVP;
- публичная документация;
- `.gitignore` для приватных project rules.

Legacy-модули не удаляются в этой версии.

## Критерии готовности

- UI не передаёт токен через command-line arguments;
- bridge возвращает account identity и liked tracks;
- Flutter показывает полученные треки;
- unit/widget tests покрывают основной локальный поток;
- README содержит полные команды подготовки, запуска, тестов и release-сборки;
- реальная авторизация отдельно проходит ручной test plan.
