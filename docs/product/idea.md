# Идея проекта

## Проблема

Музыкальная библиотека пользователя разделена между streaming provider и локальными файлами. До download/sync MusicArk должен сначала надёжно понять, какие provider tracks уже существуют локально и где система уверена в этом выводе.

## Текущий продуктовый сценарий

```text
Yandex Music cache
        +
Local Library index
        ↓
Matching
        ↓
matched / conflict / unmatched
```

Пользователь может проверить сомнительные случаи, вручную принять правильный local candidate или отклонить неверный. Эти решения сохраняются и становятся основой для Missing Tracks и будущего sync.

## Принцип качества

Для автоматического matching **precision важнее recall**. Неверный auto-match опаснее, чем `conflict` или `unmatched`, потому что следующие версии будут строить решения поверх этого dataset.

## Архитектурный принцип

Yandex integration, Local Library scanning и Matching остаются отдельными boundaries. Matching работает локально поверх уже сохранённых данных и не отправляет local metadata во внешние сервисы.

## Последовательность продукта

```text
v0.1 Yandex Likes
v0.2 Persistent Library
v0.3 Yandex Library / Playlists
v0.4 Local Library
v0.5 Matching
v0.6 Missing Tracks
v0.7 Download
v0.8 Sync
```

Download и sync не должны внедряться раньше, чем matching dataset станет достаточно надёжным.

## Риски

- provider metadata и local tags могут быть неполными или отличаться между релизами;
- live/remix/remaster/single/album версии могут выглядеть почти одинаково;
- одинаковые title у разных artists создают false-positive risk;
- качество автоматического matching нельзя подтвердить только synthetic tests — нужна проверка на реальной библиотеке;
- Yandex provider использует внешнюю integration dependency и может менять поведение независимо от local matching.

## Safety

MusicArk Matching не изменяет аудиофайлы и не мутирует Yandex Music. Manual review изменяет только локальные записи MusicArk о соответствии сущностей.
