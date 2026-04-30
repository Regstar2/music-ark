# MusicArk — карта версий

## Назначение

Эта карта описывает последовательность разработки MusicArk по версиям.

Каждая версия является отдельным этапом с понятной целью, границами, зависимостями и связями с модулями из карты проекта.

## Главная идея roadmap

```text
Сначала строим устойчивое ядро и модели.
Потом подключаем Яндекс Музыку.
Потом добавляем локальный архив.
Потом выносим загрузки в универсальную систему.
Потом делаем UI.
Потом Android и будущие расширения.
```

## Последовательность версий

- [[v0.1-core-foundation]]
- [[v0.2-provider-architecture]]
- [[v0.3-yandex-scan]]
- [[v0.4-local-library]]
- [[v0.5-download-system]]
- [[v0.6-yandex-download]]
- [[v0.7-matching]]
- [[v0.8-sync-planner]]
- [[v0.9-desktop-ui]]
- [[v0.10-metadata-editor]]
- [[v0.11-restore-upload-experimental]]
- [[v1.0-stable-desktop-mvp]]
- [[v1.1-android-mvp]]
- [[future-torrent-support]]
- [[future-providers-support]]

## Версионная цепочка

```text
[[v0.1-core-foundation]]
-> [[v0.2-provider-architecture]]
-> [[v0.3-yandex-scan]]
-> [[v0.4-local-library]]
-> [[v0.5-download-system]]
-> [[v0.6-yandex-download]]
-> [[v0.7-matching]]
-> [[v0.8-sync-planner]]
-> [[v0.9-desktop-ui]]
-> [[v0.10-metadata-editor]]
-> [[v0.11-restore-upload-experimental]]
-> [[v1.0-stable-desktop-mvp]]
-> [[v1.1-android-mvp]]
```

## Будущие направления

- [[future-torrent-support]]
- [[future-providers-support]]

## Ключевые модули из карты проекта

- [[core]]
- [[providers]]
- [[provider-capabilities]]
- [[yandex-music-provider]]
- [[local-library-provider]]
- [[download-system]]
- [[download-task]]
- [[download-provider]]
- [[local-archive]]
- [[local-audio-file]]
- [[matching-engine]]
- [[sync-planner]]
- [[sync-executor]]
- [[metadata-engine]]
- [[ui]]
- [[platform-bridge]]
- [[storage]]
- [[history-audit-log]]
- [[risks]]

## Важное правило

Версии должны строиться вертикально, но без архитектурного самоубийства.

То есть сначала делаем реально работающий путь для Яндекс Музыки, но модели называем не `YandexEverything`, а универсально: [[track]], [[track-source]], [[download-task]], [[local-audio-file]].

Два дня экономии на названиях обычно превращаются в два месяца рефакторинга. Прекрасная сделка, если ненавидеть себя будущего.
