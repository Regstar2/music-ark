# Roadmap

Roadmap фиксирует последовательность, а не обещание сроков.

## v0.1.0 — Yandex likes MVP

Статус: **подтверждено ручным Windows-тестом**.

- запуск приложения;
- вход по token;
- реальный аккаунт;
- реальный список «Мне нравится».

## v0.2.0 — Persistent Library

Текущая версия разработки.

- secure token storage;
- автоматическое восстановление сессии;
- SQLite cache «Мне нравится»;
- cache-first/offline behavior;
- snapshot replacement с удалениями;
- поиск;
- сортировка;
- last updated / sync diff.

## v0.3.0 — Standalone Windows App

Цель: убрать зависимость release-build от внешнего checkout и отдельно установленного Python environment.

## v0.4.0 — Yandex Library Expansion

Кандидаты после стабильной v0.3:

- playlists;
- дополнительные provider-library surfaces;
- улучшенная навигация библиотеки.

## v0.5.0 — Local Library

Возврат локального индексирования только после устойчивого remote-library слоя.

## v0.6+

Последовательно, а не одним релизом:

- matching;
- downloads;
- sync planning/execution.

Legacy-функции не возвращаются в UI автоматически только потому, что их код уже существует.
