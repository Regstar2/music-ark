# Идея проекта

## Проблема

Музыкальная библиотека пользователя разделена между streaming provider и локальными файлами. До download/sync MusicArk должен сначала надёжно понять, какие provider tracks уже существуют локально, какие доказанно отсутствуют и где система ещё не имеет достаточных оснований для вывода.

## Текущий продуктовый сценарий

```text
Yandex Music cache
        +
Local Library index
        ↓
Identity Matching
        ↓
matched / conflict / unmatched
        ↓
Variant Verification (secondary)
        ↓
Library Coverage
        ↓
covered / missing / needs_review / not_analyzed
```

Пользователь может проверить сомнительные matching cases, вручную принять правильный local candidate или отклонить неверный. В v0.6 он также может пометить технически missing трек как `wanted` или `ignored`; это решение не изменяет ни Matching, ни Yandex.

## Принцип качества

Для автоматического matching **precision важнее recall**. Неверный auto-match опаснее, чем `conflict` или `unmatched`, потому что следующие версии строят решения поверх этого dataset.

Для Coverage действует тот же принцип честности: `not matched` не означает `missing`. Только актуальный authoritative `UNMATCHED` считается доказанно отсутствующим. `CONFLICT`, stale state и отсутствие актуального анализа остаются отдельными состояниями.

Рядом с Local coverage показывается доля Matching analyzed, чтобы пользователь не принимал неизвестные состояния за доказанное отсутствие.

## Архитектурный принцип

Yandex integration, Local Library scanning, Identity Matching, Variant Verification и Library Coverage остаются отдельными boundaries. Coverage потребляет существующие authoritative результаты и не строит второй matching engine. Аналитика работает локально поверх уже сохранённых данных и не отправляет local metadata/missing list во внешние сервисы.

Reference audio v0.5.1 также остаётся отдельной verification-сущностью: bounded exact-reference acquisition для explicit single-track verification не делает файл Local Library и не создаёт coverage.

## Последовательность продукта

```text
v0.1   Yandex Likes
v0.2   Persistent Library
v0.3   Yandex Library / Playlists
v0.4   Local Library
v0.5.0 Identity Matching
v0.5.1 Variant Detection
v0.6   Missing Tracks / Coverage
v0.7   Download
v0.8   Sync
```

Download и sync не должны внедряться раньше, чем identity/coverage dataset станет достаточно надёжным. v0.7 получает простой вход: `coverage_status = missing AND user_action = wanted`.

## Риски

- provider metadata и local tags могут быть неполными или отличаться между релизами;
- live/remix/remaster/single/album версии могут выглядеть почти одинаково;
- одинаковые title у разных artists создают false-positive risk;
- stale matching state нельзя продолжать показывать как доказанный Missing;
- качество автоматического matching/coverage нельзя подтвердить только synthetic tests — нужна проверка на реальной библиотеке;
- Yandex provider использует внешнюю integration dependency и может менять поведение независимо от local analytics.

## Safety

MusicArk Matching/Coverage не изменяют аудиофайлы и не мутируют Yandex Music. Manual review и wanted/ignored изменяют только локальные записи MusicArk о соответствии/приоритете сущностей. v0.6 не выполняет download.
