# Scope текущего MVP

## Версия

v0.2.0 — Persistent Library.

## Цель

Перевести подтверждённый v0.1 flow из одноразовой демонстрации в устойчивое desktop-приложение:

`первый вход -> secure session -> cached library -> следующий запуск без token -> refresh`.

## Входит

- secure token persistence через OS credential store;
- bootstrap без сети;
- SQLite snapshot «Мне нравится»;
- network refresh без потери последнего cache при ошибке;
- добавление/удаление membership при snapshot replacement;
- поиск title/artist/album;
- сортировка;
- last-update timestamp;
- sync diff;
- logout с очисткой credential/cache;
- Python/Flutter tests;
- полный набор run/test/build команд.

## Не входит

- standalone Python packaging;
- playlists;
- download queue;
- matching;
- sync planner/executor;
- metadata editor;
- local library UI;
- experimental upload.

## Критерии готовности

- первый sign-in сохраняет token только в secure credential backend;
- повторный запуск не требует token;
- cached tracks доступны до network refresh;
- failed refresh не очищает cache;
- track, удалённый из Yandex Liked, исчезает после следующего успешного snapshot;
- logout очищает credential и cache;
- поиск и сортировка работают на cached/network data одинаково;
- Python tests проходят;
- `flutter analyze` проходит;
- Flutter widget tests проходят;
- ручной Windows test plan пройден.
